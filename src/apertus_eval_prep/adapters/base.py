"""Adapter contract shared by every model/system under test.

The adapter is the only component allowed to talk to a model. Everything above
it (runner, evaluators, metrics, reporting) consumes :class:`AdapterResponse`
objects, so an offline mock, a local transformers model, and a remote
OpenAI-compatible endpoint are interchangeable from the platform's point of view.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from apertus_eval_prep.core.errors import AdapterError, AdapterResponseError, AdapterTimeoutError

__all__ = [
    "AdapterCapabilities",
    "AdapterError",
    "AdapterResponse",
    "AdapterResponseError",
    "AdapterTimeoutError",
    "CompletionRequest",
    "ModelAdapter",
    "ToolCall",
    "ToolSpecView",
    "Usage",
    "estimate_tokens",
]


@dataclass(frozen=True)
class Usage:
    """Token accounting as reported by the backend (``None`` = not reported)."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True)
class ToolCall:
    """One requested tool invocation (arguments are validated by the task layer)."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "arguments": dict(self.arguments), "call_id": self.call_id}


@dataclass(frozen=True)
class ToolSpecView:
    """Read-only view of a tool made available to the model."""

    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass
class AdapterResponse:
    """One completion, plus the metadata needed for cost/latency/failure analysis."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage | None = None
    latency_ms: float = 0.0
    finish_reason: str = "stop"
    error: str | None = None
    error_code: str | None = None
    simulated: bool = False
    raw: dict[str, Any] | None = None
    seed: int | None = None
    variant: str | None = None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "text": self.text,
            "tool_calls": [call.to_dict() for call in self.tool_calls],
            "usage": self.usage.to_dict() if self.usage else None,
            "latency_ms": self.latency_ms,
            "finish_reason": self.finish_reason,
            "error": self.error,
            "error_code": self.error_code,
            "simulated": self.simulated,
        }
        if self.seed is not None:
            payload["seed"] = self.seed
        if self.variant is not None:
            payload["variant"] = self.variant
        return payload


@dataclass
class CompletionRequest:
    """Everything one completion needs; conditions make variance studies possible."""

    prompt: str
    system_prompt: str | None = None
    messages: list[dict[str, str]] | None = None
    tools: list[ToolSpecView] = field(default_factory=list)
    max_new_tokens: int = 256
    temperature: float = 0.0
    top_p: float = 1.0
    seed: int = 0
    stop: list[str] = field(default_factory=list)
    example_id: str | None = None
    conditions: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    step: int = 0

    def cache_key(self) -> str:
        from apertus_eval_prep.utils.hashing import stable_hash

        return stable_hash(
            {
                "prompt": self.prompt,
                "system": self.system_prompt,
                "messages": self.messages,
                "tools": [t.name for t in self.tools],
                "max_new_tokens": self.max_new_tokens,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "seed": self.seed,
                "step": self.step,
                "conditions": self.conditions,
            }
        )


@dataclass(frozen=True)
class AdapterCapabilities:
    """What a backend can do, so the runner never assumes a feature exists."""

    supports_tools: bool = False
    supports_system_prompt: bool = True
    supports_seed: bool = False
    reports_usage: bool = False
    deterministic: bool = False
    runs_locally: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "supports_tools": self.supports_tools,
            "supports_system_prompt": self.supports_system_prompt,
            "supports_seed": self.supports_seed,
            "reports_usage": self.reports_usage,
            "deterministic": self.deterministic,
            "runs_locally": self.runs_locally,
        }


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token) used only when a backend reports none.

    This is a documented heuristic, never presented as a measured token count.
    """
    return 0 if not text else max(1, len(text) // 4)


class ModelAdapter(ABC):
    """Base class for model adapters."""

    kind: str = "abstract"

    def __init__(
        self,
        *,
        name: str,
        model_id: str,
        revision: str | None = None,
        seed: int = 0,
        capabilities: AdapterCapabilities | None = None,
    ) -> None:
        self.name = name
        self.model_id = model_id
        self.revision = revision
        self.seed = seed
        self.capabilities = capabilities or AdapterCapabilities()

    @abstractmethod
    def complete(self, request: CompletionRequest) -> AdapterResponse:
        """Return one completion; raise AdapterError subclasses on failure."""

    @property
    def evidence_class(self) -> str:
        """``MEASURED`` for real systems, ``MOCK`` for synthetic fixtures."""
        return "MEASURED"

    def describe(self) -> dict[str, Any]:
        """Provenance block written into the run manifest."""
        return {
            "kind": self.kind,
            "name": self.name,
            "model_id": self.model_id,
            "revision": self.revision,
            "capabilities": self.capabilities.to_dict(),
            "evidence_class": self.evidence_class,
        }

    def health(self) -> dict[str, Any]:
        """Cheap self-check used by the CLI before a run starts."""
        return {"adapter": self.name, "kind": self.kind, "status": "ok"}
