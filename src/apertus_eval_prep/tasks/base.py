"""Typed task and dataset primitives shared by the evaluation platform."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from apertus_eval_prep.core.errors import DatasetError, SchemaValidationError


@dataclass
class TaskExample:
    """One immutable, auditable evaluation example."""

    example_id: str
    task: str
    prompt: str
    gold: str | None = None
    language: str | None = None
    locale: str | None = None
    domain: str | None = None
    risk_category: str | None = None
    deployment_environment: str | None = None
    split: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], *, index: int = 0) -> "TaskExample":
        if not isinstance(raw, Mapping):
            raise SchemaValidationError(f"dataset[{index}]", "must be a JSON object")
        example_id = raw.get("example_id") or raw.get("id")
        prompt = raw.get("prompt") or raw.get("input") or raw.get("user_request")
        if not isinstance(example_id, str) or not example_id.strip():
            raise SchemaValidationError(f"dataset[{index}].id", "is required and must be a string")
        if not isinstance(prompt, str) or not prompt.strip():
            raise SchemaValidationError(f"dataset[{index}].prompt", "is required and must be a string")
        task = raw.get("task") or raw.get("category") or "default"
        if not isinstance(task, str) or not task.strip():
            raise SchemaValidationError(f"dataset[{index}].task", "must be a non-empty string")
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), Mapping) else {}
        return cls(
            example_id=example_id.strip(), task=task.strip(), prompt=prompt,
            gold=None if raw.get("gold") is None else str(raw.get("gold")),
            language=_optional_str(raw.get("language")), locale=_optional_str(raw.get("locale")),
            domain=_optional_str(raw.get("domain")), risk_category=_optional_str(raw.get("risk_category")),
            deployment_environment=_optional_str(raw.get("deployment_environment")),
            split=_optional_str(raw.get("split")), metadata=dict(metadata),
        )

    def to_dict(self, *, include_prompt: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "example_id": self.example_id, "id": self.example_id, "task": self.task,
            "language": self.language, "locale": self.locale, "domain": self.domain,
            "risk_category": self.risk_category,
            "deployment_environment": self.deployment_environment,
            "split": self.split, "metadata": dict(self.metadata),
        }
        if include_prompt:
            payload["prompt"] = self.prompt
        if self.gold is not None:
            payload["gold"] = self.gold
        return payload


@dataclass
class TaskBatch:
    """Loaded examples plus the path identity used in provenance."""

    path: Path
    examples: list[TaskExample]
    requested_tasks: tuple[str, ...] = ()
    split: str | None = None

    def __iter__(self):
        return iter(self.examples)

    def __len__(self) -> int:
        return len(self.examples)


class Task(ABC):
    """Small public task interface used by runners and extension authors."""

    kind: str = "task"

    @abstractmethod
    def metadata_for(self, example: TaskExample) -> dict[str, Any]:
        """Return evaluator metadata without mutating the example."""

    def prompt_for(self, example: TaskExample) -> str:
        return example.prompt

    def score(self, example: TaskExample, output: str) -> dict[str, Any]:
        gold = example.gold
        correct = gold is not None and output.strip() == gold.strip()
        return {"score": 1.0 if correct else 0.0, "correct": correct}


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _read_records(path: Path) -> list[Mapping[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DatasetError(f"unable to read dataset: {path}", path=str(path)) from exc
    stripped = text.lstrip()
    if not stripped:
        raise DatasetError("dataset is empty", path=str(path))
    if stripped.startswith("["):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise DatasetError(f"invalid JSON dataset: {exc}", path=str(path)) from exc
        if not isinstance(payload, list):
            raise DatasetError("JSON dataset must contain an array", path=str(path))
        return [item for item in payload if isinstance(item, Mapping)]
    records: list[Mapping[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DatasetError(f"invalid JSONL at line {line_no}: {exc}", path=str(path)) from exc
        if not isinstance(item, Mapping):
            raise DatasetError(f"dataset line {line_no} must be an object", path=str(path))
        records.append(item)
    return records


def load_task_examples(
    path: str | Path, *, tasks: Iterable[str] | None = None,
    limit: int | None = None, split: str | None = None,
) -> TaskBatch:
    """Load, filter, and validate a JSON/JSONL task file."""
    dataset_path = Path(path)
    if not dataset_path.exists() or not dataset_path.is_file():
        raise DatasetError("dataset not found", path=str(dataset_path))
    requested = tuple(str(item) for item in (tasks or ()) if str(item))
    examples: list[TaskExample] = []
    seen: set[str] = set()
    for index, raw in enumerate(_read_records(dataset_path)):
        example = TaskExample.from_mapping(raw, index=index)
        if requested and example.task not in requested:
            continue
        if split is not None and example.split not in (None, split):
            continue
        if example.example_id in seen:
            raise DatasetError(f"duplicate example id: {example.example_id}", path=str(dataset_path))
        seen.add(example.example_id)
        examples.append(example)
        if limit is not None and len(examples) >= limit:
            break
    if not examples:
        detail = f" after filters tasks={list(requested)!r}" if requested else ""
        raise DatasetError(f"no examples available{detail}", path=str(dataset_path))
    return TaskBatch(dataset_path, examples, requested, split)


load_examples = load_task_examples

__all__ = ["TaskExample", "TaskBatch", "Task", "load_task_examples", "load_examples"]
