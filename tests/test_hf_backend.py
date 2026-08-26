import pytest

from apertus_eval_prep.backends.hf import load_dtype, resolve_dtype, suppress_quantization_warnings
from apertus_eval_prep.backends.hf_load import load_causal_lm, patch_stale_cache_api
from apertus_eval_prep.config import RunConfig


def _cfg(**kwargs) -> RunConfig:
    base = dict(
        model_id="m",
        tokenizer_id=None,
        revision=None,
        backend="hf",
        chat_template="tokenizer",
        quantization="none",
        seed=0,
        temperature=0.0,
        top_p=1.0,
        prompt_id="default",
        paraphrase_id="orig",
        dtype="auto",
        data_path="data/eval_set.jsonl",
        fewshot_path=None,
        experiment_id="test",
        run_id="hf-dtype-test",
        tasks=["arc_easy"],
        max_new_tokens=32,
        system_prompt=None,
        limit=None,
        batch_size=1,
    )
    base.update(kwargs)
    return RunConfig(**base)


def test_load_dtype_uses_fp16_for_quantized_cuda():
    cfg = _cfg(quantization="int8")
    assert load_dtype(cfg, "cuda") == resolve_dtype("float16", "cuda")
    assert load_dtype(_cfg(quantization="none"), "cuda") == resolve_dtype("auto", "cuda")


def test_quant_device_map_pins_gpu0():
    from apertus_eval_prep.backends.hf import _quant_device_map

    assert _quant_device_map() == {"": 0}


def test_suppress_quantization_warnings_is_noop():
    suppress_quantization_warnings()


def test_cache_shim_exposes_seen_tokens():
    pytest.importorskip("transformers")
    patch_stale_cache_api()
    from transformers.cache_utils import Cache, DynamicCache

    assert hasattr(Cache, "seen_tokens")
    cache = DynamicCache()
    assert int(cache.seen_tokens) >= 0
    assert hasattr(cache, "get_max_length")


def test_load_causal_lm_falls_back_to_remote():
    calls: list[bool] = []

    def fake_from_pretrained(_model_id, **kwargs):
        calls.append(bool(kwargs.get("trust_remote_code")))
        if not kwargs.get("trust_remote_code"):
            raise ValueError("Loading this model requires trust_remote_code=True")
        return "ok"

    assert load_causal_lm("org/custom", {"revision": None}, from_pretrained=fake_from_pretrained) == "ok"
    assert calls == [False, True]


def test_load_causal_lm_uses_native_when_available():
    def fake_from_pretrained(_model_id, **kwargs):
        assert kwargs.get("trust_remote_code") is False
        return "native"

    assert (
        load_causal_lm(
            "microsoft/Phi-3.5-mini-instruct",
            {"revision": None},
            from_pretrained=fake_from_pretrained,
        )
        == "native"
    )


def test_load_causal_lm_reraises_other_value_errors():
    def fake_from_pretrained(_model_id, **kwargs):
        raise ValueError("weights are corrupt")

    with pytest.raises(ValueError, match="corrupt"):
        load_causal_lm("org/m", {}, from_pretrained=fake_from_pretrained)
