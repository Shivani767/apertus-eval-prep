import pytest

from apertus_eval_prep.backends.hf_load import load_causal_lm, patch_stale_cache_api


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
