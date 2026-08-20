from apertus_eval_prep.backends.hf import _load_causal_lm, _patch_stale_cache_api


def test_cache_shim_exposes_seen_tokens():
    _patch_stale_cache_api()
    from transformers.cache_utils import Cache, DynamicCache

    assert hasattr(Cache, "seen_tokens")
    cache = DynamicCache()
    assert int(cache.seen_tokens) >= 0
    assert hasattr(cache, "get_max_length")


def test_load_causal_lm_falls_back_to_remote(monkeypatch):
    calls: list[bool] = []

    def fake_from_pretrained(_model_id, **kwargs):
        calls.append(bool(kwargs.get("trust_remote_code")))
        if not kwargs.get("trust_remote_code"):
            raise ValueError("Loading this model requires trust_remote_code=True")
        return "ok"

    monkeypatch.setattr(
        "apertus_eval_prep.backends.hf.AutoModelForCausalLM.from_pretrained",
        fake_from_pretrained,
    )
    assert _load_causal_lm("org/custom", {"revision": None}) == "ok"
    assert calls == [False, True]


def test_load_causal_lm_uses_native_when_available(monkeypatch):
    def fake_from_pretrained(_model_id, **kwargs):
        assert kwargs.get("trust_remote_code") is False
        return "native"

    monkeypatch.setattr(
        "apertus_eval_prep.backends.hf.AutoModelForCausalLM.from_pretrained",
        fake_from_pretrained,
    )
    assert _load_causal_lm("microsoft/Phi-3.5-mini-instruct", {"revision": None}) == "native"
