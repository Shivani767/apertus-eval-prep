"""The prompt protocol is part of the claim, so it must be explicit and recorded.

Four of the seven curated models scored exactly 0.0000 on a letter-only task
because the adapter concatenated system and user text and handed it to the
tokenizer raw. An instruct model served raw text continues the passage instead
of replying, so the answer never appears where the extractor looks. The fix is
`apply_chat_template`; these tests pin it so it cannot regress silently, and
pin the default so existing configurations keep their exact behaviour.
"""

from __future__ import annotations

import pytest

from apertus_eval_prep.adapters.base import CompletionRequest
from apertus_eval_prep.adapters.local_transformers import LocalTransformersAdapter
from apertus_eval_prep.core.errors import AdapterGenerationError, AdapterResponseError


class _FakeTokenizer:
    """Minimal stand-in exposing only what the adapter actually touches."""

    def __init__(self, chat_template: str = "<tpl>") -> None:
        self.chat_template = chat_template
        self.calls: list[dict] = []

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False):
        self.calls.append({
            "messages": messages,
            "tokenize": tokenize,
            "add_generation_prompt": add_generation_prompt,
        })
        body = "\n".join(f"<{m['role']}>{m['content']}</{m['role']}>" for m in messages)
        return f"{body}<assistant>" if add_generation_prompt else body


def _adapter(**params) -> LocalTransformersAdapter:
    return LocalTransformersAdapter(
        name="local-test", model_id="org/model", revision="abc123", params=params
    )


def _request(prompt: str = "Reply with the letter only.", system_prompt: str | None = None):
    return CompletionRequest(
        prompt=prompt,
        system_prompt=system_prompt,
        max_new_tokens=8,
        temperature=0.0,
        top_p=1.0,
    )


def test_without_the_flag_the_prompt_is_raw_text():
    """Default behaviour is unchanged, so existing configs keep their semantics."""
    adapter = _adapter()
    adapter._tokenizer = _FakeTokenizer()
    assert adapter._build_prompt(_request(system_prompt="be brief")) == (
        "be brief\n\nReply with the letter only."
    )
    assert adapter._tokenizer.calls == []  # the template is genuinely not used


def test_no_system_prompt_means_no_prefix():
    adapter = _adapter()
    adapter._tokenizer = _FakeTokenizer()
    assert adapter._build_prompt(_request()) == "Reply with the letter only."


def test_the_flag_routes_through_the_tokenizer_template():
    adapter = _adapter(apply_chat_template=True)
    tokenizer = _FakeTokenizer()
    adapter._tokenizer = tokenizer
    built = adapter._build_prompt(_request(system_prompt="be brief"))
    assert built.endswith("<assistant>")
    assert "<system>be brief</system>" in built
    assert "<user>Reply with the letter only.</user>" in built
    assert tokenizer.calls[0]["add_generation_prompt"] is True
    assert tokenizer.calls[0]["tokenize"] is False


def test_system_turn_is_omitted_when_absent():
    adapter = _adapter(apply_chat_template=True)
    adapter._tokenizer = _FakeTokenizer()
    assert "<system>" not in adapter._build_prompt(_request())


def test_a_broken_template_raises_instead_of_falling_back_to_raw_text():
    """Silently serving raw text is the bug; it must not return as a fallback."""

    class Broken(_FakeTokenizer):
        def apply_chat_template(self, *a, **k):
            raise ValueError("no template for this model")

    adapter = _adapter(apply_chat_template=True)
    adapter._tokenizer = Broken()
    with pytest.raises(AdapterGenerationError) as caught:
        adapter._build_prompt(_request())
    assert "apply_chat_template: false" in str(caught.value)


def test_the_protocol_is_recorded_in_the_manifest():
    adapter = _adapter(apply_chat_template=True)
    adapter._tokenizer = _FakeTokenizer()
    payload = adapter.describe()
    assert payload["apply_chat_template"] is True
    assert "warnings" not in payload


def test_serving_an_instruct_model_raw_records_a_warning():
    adapter = _adapter()
    adapter._tokenizer = _FakeTokenizer(chat_template="<tpl>")
    payload = adapter.describe()
    assert payload["apply_chat_template"] is False
    assert any("chat template" in w for w in payload["warnings"])


def test_no_warning_when_the_tokenizer_has_no_template():
    """A base model has no template, so raw text is correct and must stay quiet."""
    adapter = _adapter()
    adapter._tokenizer = _FakeTokenizer(chat_template="")
    assert "warnings" not in adapter.describe()


def test_the_flag_must_be_a_boolean():
    with pytest.raises(AdapterResponseError):
        _adapter(apply_chat_template="yes")
