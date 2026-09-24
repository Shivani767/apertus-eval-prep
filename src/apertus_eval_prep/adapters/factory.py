"""Adapter construction with explicit, offline-safe defaults."""
from __future__ import annotations

from typing import Any

from apertus_eval_prep.adapters.base import ModelAdapter
from apertus_eval_prep.adapters.mock import MockAdapter
from apertus_eval_prep.core.errors import AdapterError
from apertus_eval_prep.core.schemas import AdapterSpec


def adapter_from_spec(spec: AdapterSpec, *, seed: int = 0) -> ModelAdapter:
    """Build an adapter from a validated spec.

    Only the mock adapter is constructed without optional model/runtime
    dependencies.  Local and OpenAI-compatible adapters are intentionally
    explicit and fail with an actionable message when their backend is absent.
    """
    params: dict[str, Any] = dict(spec.params or {})
    if spec.kind == "mock":
        return MockAdapter.from_params(
            params, name=spec.name, model_id=spec.model_id, revision=spec.revision, seed=seed
        )
    if spec.kind == "local":
        from apertus_eval_prep.adapters.local import LocalAdapter

        return LocalAdapter.from_params(
            params, name=spec.name, model_id=spec.model_id, revision=spec.revision, seed=seed
        )
    if spec.kind == "openai_compatible":
        from apertus_eval_prep.adapters.openai_compatible import OpenAICompatibleAdapter

        return OpenAICompatibleAdapter.from_params(
            params, name=spec.name, model_id=spec.model_id, revision=spec.revision, seed=seed
        )
    raise AdapterError(f"unsupported adapter kind: {spec.kind!r}")


__all__ = ["adapter_from_spec"]
