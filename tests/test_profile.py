"""Tests for runtime profiling — synthetic blob only (no model calls)."""

from apertus_eval_prep.profile import render_profile_markdown, runtime_profile

BLOB = {
    "manifest": {
        "settings": {"model_id": "synthetic/model", "backend": "hf",
                     "quantization": None},
        "hardware": {"gpu": "test"},
    },
    "items": [
        {"id": "a1", "task": "gsm8k", "language": "en", "correct": True,
         "tokens_per_sec": 10.0, "e2e_ms": 100.0, "ttft_ms": 20.0,
         "num_new_tokens": 10, "prompt_tokens": 50},
        {"id": "a2", "task": "gsm8k", "language": "en", "correct": False,
         "tokens_per_sec": 20.0, "e2e_ms": 200.0, "ttft_ms": 40.0,
         "num_new_tokens": 20, "prompt_tokens": 60},
        {"id": "a3", "task": "mgsm", "language": "de", "correct": True,
         "tokens_per_sec": 5.0, "e2e_ms": 400.0,
         "num_new_tokens": 20, "prompt_tokens": 80},
        # item with NO timing fields at all — must not crash, must not zero-fill
        {"id": "a4", "task": "mgsm", "language": "de", "correct": False},
    ],
}

# mimics the committed vLLM run: e2e_ms recorded as 0.0 placeholders
VLLM_LIKE = {
    "manifest": {"settings": {"model_id": "synthetic/vllm", "backend": "vllm"},
                 "hardware": {"gpu": "test"}},
    "items": [
        {"id": f"v{i}", "task": "gsm8k", "language": "en", "correct": True,
         "e2e_ms": 0.0, "ttft_ms": None, "tokens_per_sec": None}
        for i in range(5)
    ],
}


def test_vllm_zero_placeholders_are_not_measurements():
    prof = runtime_profile(VLLM_LIKE)
    g = prof["overall"]
    assert g["n_e2e_zero_placeholder"] == 5
    assert g["e2e_ms"]["mean"] is None and g["e2e_ms"]["n"] == 0
    text = render_profile_markdown(prof)
    assert "n/a" in text  # rendered as unavailable, not 0.0


def test_profile_groups_and_missing_handling():
    prof = runtime_profile(BLOB)
    assert prof["model_id"] == "synthetic/model"
    assert prof["overall"]["n_items"] == 4
    assert prof["overall"]["accuracy"] == 0.5
    assert prof["by_task"]["gsm8k"]["tokens_per_sec"]["mean"] == 15.0
    # de group: only one item has tokens_per_sec -> n=1, no zero-fill
    de = prof["by_language"]["de"]
    assert de["n_items"] == 2
    assert de["tokens_per_sec"] == {"mean": 5.0, "median": 5.0, "n": 1}
    assert de["ttft_ms"]["n"] == 0 and de["ttft_ms"]["mean"] is None


def test_render_markdown_contains_tables_and_provenance():
    text = render_profile_markdown(runtime_profile(BLOB))
    assert "## By task" in text and "## By language" in text
    assert "| de | 2 | 0.5 | 5.0 |" in text
    assert "DERIVED from measured per-item timing records" in text
    assert "zero-filled" in text


def test_empty_blob_is_honest():
    prof = runtime_profile({"manifest": {"settings": {}}, "items": []})
    assert prof["overall"]["n_items"] == 0
    assert prof["overall"]["accuracy"] is None
    assert prof["overall"]["tokens_per_sec"]["mean"] is None