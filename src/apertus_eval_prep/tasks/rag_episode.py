"""RAG episode schemas and deterministic task adapter."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from apertus_eval_prep.core.errors import DatasetError, SchemaValidationError
from apertus_eval_prep.tasks.base import Task, TaskExample
from apertus_eval_prep.utils.pii import redact_structure


@dataclass
class ToolTrace:
    """One sanitized, auditable step in an offline tool-using episode."""

    episode_id: str
    step: int
    tool_name: str
    input_arguments: dict[str, Any] = field(default_factory=dict)
    schema_valid: bool = False
    schema_validation: dict[str, Any] = field(default_factory=dict)
    result_status: str = "unknown"
    latency_ms: float = 0.0
    error_type: str | None = None
    retry_count: int = 0
    recovered: bool = False
    result: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def step_number(self) -> int:
        """Human-facing one-based step number; ``step`` remains zero-based."""
        return self.step + 1

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "ToolTrace":
        if not isinstance(raw, Mapping):
            raise SchemaValidationError("tool_trace", "must be an object")
        step = raw.get("step")
        if step is None and "step_number" in raw:
            try:
                step = int(raw["step_number"]) - 1
            except (TypeError, ValueError) as exc:
                raise SchemaValidationError("tool_trace.step_number", "must be an integer") from exc
        if step is None:
            step = 0
        try:
            step_number = int(step)
        except (TypeError, ValueError) as exc:
            raise SchemaValidationError("tool_trace.step", "must be an integer") from exc
        if step_number < 0:
            raise SchemaValidationError("tool_trace.step", "must be >= 0")
        raw_arguments = raw.get("input_arguments") or raw.get("arguments") or {}
        raw_result = raw.get("result") or {}
        raw_validation = raw.get("schema_validation") or {}
        arguments = redact_structure(dict(raw_arguments) if isinstance(raw_arguments, Mapping) else {})
        result = redact_structure(dict(raw_result) if isinstance(raw_result, Mapping) else {})
        validation = redact_structure(dict(raw_validation) if isinstance(raw_validation, Mapping) else {})
        return cls(
            episode_id=str(raw.get("episode_id") or ""),
            step=step_number,
            tool_name=str(raw.get("tool_name") or raw.get("name") or ""),
            input_arguments=arguments,
            schema_valid=bool(raw.get("schema_valid", raw.get("valid", False))),
            schema_validation=validation,
            result_status=str(raw.get("result_status") or raw.get("status") or "unknown"),
            latency_ms=float(raw.get("latency_ms") or 0.0),
            error_type=None if raw.get("error_type") is None else str(raw.get("error_type")),
            retry_count=int(raw.get("retry_count") or 0),
            recovered=bool(raw.get("recovered", False)),
            result=result,
            timestamp=str(raw.get("timestamp") or datetime.now(timezone.utc).isoformat()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "step": self.step,
            "step_number": self.step_number,
            "tool_name": self.tool_name,
            "input_arguments": redact_structure(dict(self.input_arguments)),
            "schema_valid": self.schema_valid,
            "schema_validation": redact_structure(dict(self.schema_validation)),
            "result_status": self.result_status,
            "latency_ms": self.latency_ms,
            "error_type": self.error_type,
            "retry_count": self.retry_count,
            "recovered": self.recovered,
            "result": redact_structure(dict(self.result)),
            "timestamp": self.timestamp,
        }


@dataclass
class Episode:
    episode_id: str
    user_request: str
    description: str = ""
    language: str | None = None
    domain: str | None = None
    initial_context: list[dict[str, Any]] = field(default_factory=list)
    available_tools: list[dict[str, Any]] = field(default_factory=list)
    expected_constraints: list[str] = field(default_factory=list)
    success_criteria: dict[str, Any] = field(default_factory=dict)
    expected_answer: str | None = None
    tool_plan: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    locale: str | None = None
    expected_sources: list[str] = field(default_factory=list)
    expected_citations: list[str] = field(default_factory=list)

    @property
    def documents(self) -> list[dict[str, Any]]:
        """Alias used by generic RAG consumers."""
        return self.initial_context

    @property
    def expected_source_ids(self) -> list[str]:
        return self.expected_sources or self.expected_citations

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], *, index: int = 0) -> "Episode":
        if not isinstance(raw, Mapping):
            raise SchemaValidationError(f"episode[{index}]", "must be an object")
        episode_id = raw.get("episode_id") or raw.get("id")
        request = raw.get("user_request") or raw.get("prompt")
        if not isinstance(episode_id, str) or not episode_id.strip() or not isinstance(request, str) or not request.strip():
            raise SchemaValidationError(f"episode[{index}]", "episode_id and user_request are required")
        context = raw.get("initial_context")
        if context is None:
            context = raw.get("documents") or []
        tools = raw.get("available_tools") or raw.get("tools") or []
        constraints = raw.get("expected_constraints") or []
        if not isinstance(context, list) or not isinstance(tools, list) or not isinstance(constraints, list):
            raise SchemaValidationError(f"episode[{index}]", "context, tools, and constraints must be lists")
        criteria = raw.get("success_criteria") or {}
        if not isinstance(criteria, Mapping):
            raise SchemaValidationError(f"episode[{index}].success_criteria", "must be an object")
        return cls(
            episode_id=episode_id.strip(), user_request=request,
            description=str(raw.get("description") or ""), language=raw.get("language"),
            domain=raw.get("domain"), locale=raw.get("locale"),
            initial_context=[dict(x) for x in context if isinstance(x, Mapping)],
            available_tools=[dict(x) for x in tools if isinstance(x, Mapping)],
            expected_constraints=[str(x) for x in constraints], success_criteria={str(k): v for k, v in criteria.items()},
            expected_answer=None if raw.get("expected_answer") is None else str(raw.get("expected_answer")),
            tool_plan=[dict(x) for x in (raw.get("tool_plan") or []) if isinstance(x, Mapping)],
            metadata=dict(raw.get("metadata") or {}),
            expected_sources=[str(x) for x in (raw.get("expected_sources") or raw.get("expected_source_ids") or [])],
            expected_citations=[str(x) for x in (raw.get("expected_citations") or raw.get("expected_source_ids") or [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {"episode_id": self.episode_id, "user_request": self.user_request,
                "description": self.description, "language": self.language, "locale": self.locale,
                "domain": self.domain, "initial_context": list(self.initial_context),
                "documents": list(self.initial_context), "available_tools": list(self.available_tools),
                "expected_constraints": list(self.expected_constraints), "success_criteria": dict(self.success_criteria),
                "expected_answer": self.expected_answer, "tool_plan": list(self.tool_plan),
                "expected_sources": list(self.expected_sources), "expected_citations": list(self.expected_citations),
                "metadata": dict(self.metadata)}


def load_episodes(
    path: str | Path, *, limit: int | None = None,
    episode_ids: list[str] | None = None, perturbations: list[str] | None = None,
) -> list[Episode]:
    source = Path(path)
    if not source.exists():
        raise DatasetError("episode dataset not found", path=str(source))
    records: list[Mapping[str, Any]] = []
    text = source.read_text(encoding="utf-8")
    if text.lstrip().startswith("["):
        payload = json.loads(text)
        if not isinstance(payload, list):
            raise DatasetError("episode JSON must contain an array", path=str(source))
        records = [item for item in payload if isinstance(item, Mapping)]
    else:
        for line_no, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            item = json.loads(line)
            if not isinstance(item, Mapping):
                raise DatasetError(f"episode line {line_no} must be an object", path=str(source))
            records.append(item)
    episodes = [Episode.from_mapping(item, index=i) for i, item in enumerate(records)]
    requested_ids = {str(item) for item in (episode_ids or []) if str(item)}
    if requested_ids:
        episodes = [episode for episode in episodes if episode.episode_id in requested_ids]
    for name in perturbations or []:
        from apertus_eval_prep.tasks.perturbations import apply_perturbation
        episodes = [Episode.from_mapping(apply_perturbation(episode.to_dict(), name), index=i)
                    for i, episode in enumerate(episodes)]
    return episodes[:limit] if limit else episodes


class RAGEpisodeTask(Task):
    """Render a context-grounded answer request for a RAG workflow."""

    kind = "rag_episode"

    def metadata_for(self, example: TaskExample) -> dict[str, Any]:
        return dict(example.metadata)

    def prompt_for(self, example: TaskExample) -> str:
        context = example.metadata.get("initial_context") or []
        rendered = "\n".join(f"[{item.get('source_id', 'source')}]: {item.get('content', '')}" for item in context)
        return f"Use only the supplied context when it is relevant.\nContext:\n{rendered}\n\nUser request: {example.prompt}"

    def score(self, example: TaskExample, output: str) -> dict[str, Any]:
        expected = example.gold or ""
        normalized = " ".join(output.lower().split())
        correct = bool(expected and expected.lower() in normalized)
        return {"score": 1.0 if correct else 0.0, "correct": correct,
                "predicted": output, "gold": expected, "scorer": "rag_heuristic"}


__all__ = ["Episode", "ToolTrace", "load_episodes", "RAGEpisodeTask"]
