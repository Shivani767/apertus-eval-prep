"""Configurable, sanitized safety taxonomy and test-case schemas."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from apertus_eval_prep.core.errors import SafetyConfigError
from apertus_eval_prep.utils.pii import redact_text_for_report
from apertus_eval_prep.utils.serialization import read_yaml

CATEGORIES: tuple[str, ...] = (
    "prompt_injection", "data_leakage", "unauthorized_instruction_override",
    "unsafe_tool_use", "harmful_content_compliance", "benign_false_refusal",
    "privacy_sensitive_output", "unsupported_high_stakes_claim", "misleading_confidence",
    "policy_bypass_attempt", "retrieval_context_manipulation",
)
SEVERITIES: tuple[str, ...] = ("low", "medium", "high", "critical")
DEFAULT_CATEGORY_WEIGHTS: dict[str, float] = {category: 1.0 for category in CATEGORIES}
DEFAULT_SEVERITY_WEIGHTS: dict[str, float] = {"low": 0.25, "medium": 0.5, "high": 1.0, "critical": 2.0}


@dataclass(frozen=True)
class SafetyCase:
    test_id: str
    category: str
    severity: str
    domain: str
    scenario: str
    prompt: str
    expected_safe_behavior: str
    expectation: str = "refuse"
    benign: bool = False
    context: str = ""
    human_review_required: bool = True
    labels: dict[str, Any] = field(default_factory=dict)
    evaluation_rubric: Any = field(default_factory=dict)
    human_review_label: Any | None = None

    @property
    def sanitized_scenario(self) -> str:
        return redact_text_for_report(self.scenario)

    @property
    def sanitized_prompt(self) -> str:
        return redact_text_for_report(self.prompt)

    @property
    def sanitized_context(self) -> str:
        return redact_text_for_report(self.context)

    def __post_init__(self) -> None:
        if not self.test_id.strip():
            raise SafetyConfigError("safety case test_id must not be empty")
        if self.category not in CATEGORIES:
            raise SafetyConfigError(f"unknown safety category: {self.category!r}")
        if self.severity not in SEVERITIES:
            raise SafetyConfigError(f"unknown safety severity: {self.severity!r}")
        if not self.prompt.strip():
            raise SafetyConfigError(f"safety case {self.test_id!r} has an empty sanitized prompt")
        if not self.expected_safe_behavior.strip():
            raise SafetyConfigError(f"safety case {self.test_id!r} has no expected safe behavior")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], *, index: int = 0) -> "SafetyCase":
        if not isinstance(raw, Mapping):
            raise SafetyConfigError(f"safety_cases[{index}] must be an object")
        test_id = raw.get("test_id") or raw.get("id")
        category = raw.get("category")
        severity = str(raw.get("severity") or "medium").lower()
        prompt = raw.get("sanitized_prompt") or raw.get("prompt")
        safe_behavior = raw.get("expected_safe_behavior") or raw.get("safe_behavior")
        rubric = raw.get("evaluation_rubric", raw.get("rubric", {}))
        human_label = raw.get("human_review_label", raw.get("human_review"))
        if not isinstance(test_id, str) or not test_id or category not in CATEGORIES:
            raise SafetyConfigError(f"safety_cases[{index}] has an invalid id or category")
        if severity not in SEVERITIES or not isinstance(prompt, str) or not prompt.strip():
            raise SafetyConfigError(f"safety_cases[{index}] has invalid severity or prompt")
        if not isinstance(safe_behavior, str) or not safe_behavior.strip():
            raise SafetyConfigError(f"safety_cases[{index}] has no expected safe behavior")
        if rubric is not None and not isinstance(rubric, (Mapping, list, tuple)):
            raise SafetyConfigError(f"safety_cases[{index}] rubric must be a mapping or list")
        labels = raw.get("labels") or {}
        if not isinstance(labels, Mapping):
            raise SafetyConfigError(f"safety_cases[{index}].labels must be a mapping")
        return cls(test_id=test_id, category=str(category), severity=severity,
                   domain=str(raw.get("domain") or "general"),
                   scenario=str(raw.get("scenario") or "sanitized scenario"),
                   prompt=prompt, expected_safe_behavior=safe_behavior,
                   expectation=str(raw.get("expectation") or ("answer" if raw.get("benign") else "refuse")),
                   benign=bool(raw.get("benign", False)), context=str(raw.get("context") or ""),
                   human_review_required=bool(raw.get("human_review_required", True)), labels=dict(labels),
                   evaluation_rubric=rubric, human_review_label=human_label)

    def to_dict(self) -> dict[str, Any]:
        safe_behavior = redact_text_for_report(self.expected_safe_behavior)
        context = self.sanitized_context
        return {
            "test_id": self.test_id, "category": self.category, "severity": self.severity,
            "domain": self.domain, "scenario": self.sanitized_scenario,
            "sanitized_scenario": self.sanitized_scenario, "sanitized_prompt": self.sanitized_prompt,
            "expected_safe_behavior": safe_behavior, "expected_behavior": safe_behavior,
            "expectation": self.expectation, "benign": self.benign, "context": context,
            "sanitized_context": context, "human_review_required": self.human_review_required,
            "labels": dict(self.labels), "evaluation_rubric": self.evaluation_rubric,
            "human_review_label": self.human_review_label,
        }


def load_safety_cases(path: str | Path) -> list[SafetyCase]:
    source = Path(path)
    if not source.exists():
        raise SafetyConfigError(f"safety case file not found: {source}")
    records: list[Mapping[str, Any]] = []
    text = source.read_text(encoding="utf-8")
    try:
        if text.lstrip().startswith("["):
            payload = json.loads(text)
            if not isinstance(payload, list):
                raise SafetyConfigError("safety JSON must contain an array")
            records = [item for item in payload if isinstance(item, Mapping)]
        else:
            for line_no, line in enumerate(text.splitlines(), start=1):
                if not line.strip():
                    continue
                item = json.loads(line)
                if not isinstance(item, Mapping):
                    raise SafetyConfigError(f"safety case line {line_no} must be an object")
                records.append(item)
    except json.JSONDecodeError as exc:
        raise SafetyConfigError(f"malformed safety case file: {source}") from exc
    cases = [SafetyCase.from_mapping(item, index=i) for i, item in enumerate(records)]
    test_ids = [case.test_id for case in cases]
    if len(set(test_ids)) != len(test_ids):
        raise SafetyConfigError("safety case test IDs must be unique")
    return cases


def load_taxonomy(path: str | Path) -> dict[str, Any]:
    """Load a versioned safety taxonomy YAML/JSON file."""
    source = Path(path)
    if not source.exists():
        raise SafetyConfigError(f"safety taxonomy file not found: {source}")
    try:
        raw = read_yaml(source) if source.suffix.lower() not in {".json", ".jsonl"} else json.loads(source.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SafetyConfigError(f"unable to load safety taxonomy: {source}") from exc
    if not isinstance(raw, Mapping):
        raise SafetyConfigError("safety taxonomy must be a mapping")
    return validate_taxonomy(raw.get("safety_taxonomy", raw))


def validate_taxonomy(raw: Mapping[str, Any] | None = None) -> dict[str, Any]:
    data = dict(raw or {})
    raw_categories = data.get("categories", CATEGORIES)
    if not isinstance(raw_categories, (list, tuple)) or not raw_categories:
        raise SafetyConfigError("taxonomy categories must be a non-empty list")
    categories = tuple(str(category) for category in raw_categories)
    if len(set(categories)) != len(categories) or any(category not in CATEGORIES for category in categories):
        raise SafetyConfigError("taxonomy contains duplicate or unknown categories")
    category_weights = {**DEFAULT_CATEGORY_WEIGHTS, **dict(data.get("category_weights") or {})}
    severity_weights = {**DEFAULT_SEVERITY_WEIGHTS, **dict(data.get("severity_weights") or {})}
    for label, weights in (("category", category_weights), ("severity", severity_weights)):
        allowed = set(CATEGORIES) if label == "category" else set(SEVERITIES)
        for key, value in weights.items():
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise SafetyConfigError(f"{label} weight for {key!r} must be numeric") from exc
            if key not in allowed or not math.isfinite(number) or number < 0:
                raise SafetyConfigError(f"invalid {label} weight: {key!r}")
    return {
        "id": str(data.get("id") or data.get("taxonomy_id") or "default"),
        "version": str(data.get("version") or "1"),
        "description": str(data.get("description") or "public-safe defensive safety taxonomy"),
        "categories": list(categories), "severities": list(SEVERITIES),
        "category_weights": category_weights, "severity_weights": severity_weights,
    }


__all__ = ["CATEGORIES", "SEVERITIES", "DEFAULT_CATEGORY_WEIGHTS", "DEFAULT_SEVERITY_WEIGHTS",
           "SafetyCase", "load_safety_cases", "load_taxonomy", "validate_taxonomy"]
