"""End-to-end: does a templated request actually change what the model sees?

The unit tests pin `_build_prompt` and `describe`. This file drives the whole
`complete()` path with a stub tokenizer and a stub model, because the bug being
guarded against was never in prompt construction logic — it was in the fact that
prompt construction was never given the tokenizer's chat format at all. If
`complete()` stops routing through `_build_prompt`, every unit test still passes
and the bug returns, so the integration seam needs its own coverage.
"""

from __future__ import annotations

import pytest

from apertus_eval_prep.adapters.base import CompletionRequest
from apertus_eval_prep.adapters.local_transformers import LocalTransformersAdapter
from apertus_eval_prep.core.errors import AdapterGenerationError


class _StubTokenizer:
    chat_template = "<tpl>"

    def __init__(self):
        self.seen: list[str] = []

    def __call__(self, text, return_tensors=None):
        self.seen.append(text)
        return {"input_ids": _Ids(len(text.split())), "attention_mask": _Ids(len(text.split()))}

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False):
        body = "".join(f"<|{m['role']}|>{m['content']}" for m in messages)
        return f"{body}<|assistant|>" if add_generation_prompt else body

    def decode(self, ids, skip_special_tokens=True):
        return "b"


class _Ids:
    """Just enough of a tensor for the adapter's length arithmetic and .to()."""

    def __init__(self, n: int) -> None:
        self.n = n

    @property
    def shape(self):
        # A property, matching torch.Tensor.shape, which the adapter indexes.
        return (1, self.n)

    def numel(self) -> int:
        return self.n
    def to(self, _device):
        return self

    def __getitem__(self, index):
        return self


class _StubModel:
    def generate(self, **kwargs):
        self.kwargs = kwargs
        return _Ids(8)

    def parameters(self):
        return iter(())


@pytest.fixture()
def wired(monkeypatch):
    """An adapter whose heavy _load() is replaced by stubs."""

    def build(**params):
        adapter = LocalTransformersAdapter(
            name="local-e2e", model_id="org/model", revision="abc123", params=params
        )
        tokenizer = _StubTokenizer()
        monkeypatch.setattr(adapter, "_load", lambda: None, raising=False)
        adapter._tokenizer = tokenizer
        adapter._model = _StubModel()
        adapter._torch = type(
            "T", (), {"device": staticmethod(lambda _d: "cpu")}
        )()
        adapter._loaded_device = "cpu"
        return adapter, tokenizer

    return build


def _request():
    return CompletionRequest(
        prompt="Which is a living organism?\nA) Granite\nB) Oak tree",
        system_prompt="Answer with the letter only.",
        max_new_tokens=4,
        temperature=0.0,
        top_p=1.0,
    )


def test_templated_run_hands_the_model_chat_formatted_text(wired):
    adapter, tokenizer = wired(apply_chat_template=True)
    adapter.complete(_request())
    assert len(tokenizer.seen) == 1
    prompt = tokenizer.seen[0]
    assert "<|user|>Which is a living organism?" in prompt
    assert "<|assistant|>" in prompt
    assert "Answer with the letter only." in prompt


def test_untemplated_run_hands_the_model_the_raw_concatenation(wired):
    """The old behaviour, preserved by default so history stays comparable."""
    adapter, tokenizer = wired()
    adapter.complete(_request())
    prompt = tokenizer.seen[0]
    assert prompt.startswith("Answer with the letter only.")
    assert "<|user|>" not in prompt and "<|assistant|>" not in prompt


def test_the_two_protocols_differ(wired):
    """The regression in one assertion: the flag changes the served prompt."""
    templated, t_tok = wired(apply_chat_template=True)
    templated.complete(_request())
    raw, r_tok = wired()
    raw.complete(_request())
    assert t_tok.seen[0] != r_tok.seen[0]


def test_a_tokenizer_without_a_template_still_serves_raw_text(wired):
    """A base model has nothing to apply; the flag cannot invent a format."""
    adapter, tokenizer = wired(apply_chat_template=True)
    tokenizer.chat_template = ""
    assert adapter._tokenizer_has_chat_template() is False


def test_template_failure_surfaces_as_a_generation_error(wired):
    class Broken(_StubTokenizer):
        def apply_chat_template(self, *a, **k):
            raise ValueError("chat_template references an unknown control token")

    adapter, _ = wired(apply_chat_template=True)
    adapter._tokenizer = Broken()
    with pytest.raises(AdapterGenerationError) as caught:
        adapter.complete(_request())
    assert "apply_chat_template: false" in str(caught.value)
