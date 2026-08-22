"""Model-load helpers with no torch import so unit tests run in CI --no-deps."""

from __future__ import annotations

from typing import Any, Callable


def patch_stale_cache_api() -> None:
    """Hub modeling_phi3.py still reads Cache APIs removed in recent transformers."""
    try:
        from transformers.cache_utils import Cache
    except ImportError:
        return
    if not hasattr(Cache, "seen_tokens"):
        Cache.seen_tokens = property(
            lambda self: int(self.get_seq_length()) if hasattr(self, "get_seq_length") else 0
        )
    if not hasattr(Cache, "get_max_length"):

        def _get_max_length(self):
            fn = getattr(self, "get_max_cache_shape", None)
            return fn() if callable(fn) else None

        Cache.get_max_length = _get_max_length


def load_causal_lm(
    model_id: str,
    load_kwargs: dict,
    from_pretrained: Callable[..., Any] | None = None,
):
    """Prefer native transformers classes. Phi-3.5 remote code crashes on DynamicCache."""
    loader = from_pretrained
    if loader is None:
        from transformers import AutoModelForCausalLM

        loader = AutoModelForCausalLM.from_pretrained
    native = dict(load_kwargs)
    native["trust_remote_code"] = False
    try:
        return loader(model_id, **native)
    except ValueError as exc:
        if "trust_remote_code" not in str(exc):
            raise
        remote = dict(load_kwargs)
        remote["trust_remote_code"] = True
        return loader(model_id, **remote)
