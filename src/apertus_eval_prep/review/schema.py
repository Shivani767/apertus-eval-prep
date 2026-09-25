"""Privacy-safe schema and normalization for human annotations."""
from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any, Mapping

from apertus_eval_prep.core.evidence import EVIDENCE_MODES
from apertus_eval_prep.utils.pii import redact_for_artifact, redact_text_for_artifact

REVIEW_DIMENSIONS: tuple[str, ...] = (
    "correctness", "instruction_following", "groundedness", "citation_source_support",
    "helpfulness", "safe_behavior", "false_refusal", "tool_use_correctness",
    "overall_preference",
)
_DIMENSION_ALIASES = {
    "safety": "safe_behavior", "tool_use": "tool_use_correctness",
    "tool-use": "tool_use_correctness", "preference": "overall_preference",
    "citation": "citation_source_support", "source_support": "citation_source_support",
}
LABELS_BY_DIMENSION: dict[str, tuple[str, ...]] = {
    "correctness": ("correct", "partially_correct", "incorrect", "insufficient_evidence"),
    "instruction_following": ("fully_compliant", "partially_compliant", "noncompliant", "insufficient_evidence"),
    "groundedness": ("supported", "partially_supported", "unsupported", "insufficient_evidence"),
    "citation_source_support": ("supported", "partially_supported", "unsupported", "not_applicable"),
    "helpfulness": ("helpful", "partially_helpful", "unhelpful", "insufficient_evidence"),
    "safe_behavior": ("safe", "unsafe", "insufficient_evidence"),
    "false_refusal": ("appropriate_response", "false_refusal", "insufficient_evidence"),
    "tool_use_correctness": ("valid", "invalid", "not_applicable", "insufficient_evidence"),
    "overall_preference": ("baseline", "candidate", "tie", "insufficient_evidence"),
}
_ADJUDICATION_STATUSES = {"not_required", "pending", "agreed", "disputed"}


class ReviewValidationError(ValueError):
    """An annotation cannot be accepted as a valid review record."""


def normalize_dimension(value: Any) -> str:
    raw = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    raw = _DIMENSION_ALIASES.get(raw, raw)
    if raw not in REVIEW_DIMENSIONS:
        raise ReviewValidationError(f"unsupported review dimension: {value!r}")
    return raw


def _identifier(record: Mapping[str, Any], key: str) -> str:
    value = str(record.get(key) or "").strip()
    if not value:
        raise ReviewValidationError(f"{key} is required")
    return value


def _score(record: Mapping[str, Any], key: str) -> float | None:
    value = record.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        raise ReviewValidationError(f"{key} must be a finite number between 0 and 1")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ReviewValidationError(f"{key} must be a finite number between 0 and 1") from exc
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ReviewValidationError(f"{key} must be a finite number between 0 and 1")
    return number


def validate_annotation(record: Mapping[str, Any], *, require_completed: bool = True) -> dict[str, Any]:
    """Validate and sanitize one annotation without mutating model artifacts."""
    if not isinstance(record, Mapping):
        raise ReviewValidationError("annotation must be a JSON object")
    data = dict(record)
    if "annotator_id" in data and data.get("annotator_id"):
        raise ReviewValidationError("use annotator_id_hash; raw annotator identifiers are not accepted")
    dimension = normalize_dimension(data.get("dimension"))
    status = str(data.get("status") or "template").strip().lower()
    if status not in {"template", "completed", "rejected"}:
        raise ReviewValidationError("status must be template, completed, or rejected")
    out: dict[str, Any] = {
        "annotation_id": _identifier(data, "annotation_id"), "study_id": _identifier(data, "study_id"),
        "run_id": _identifier(data, "run_id"), "example_id": data.get("example_id"),
        "episode_id": data.get("episode_id"), "task": data.get("task"), "domain": data.get("domain"),
        "language": data.get("language"), "dimension": dimension,
        "rubric_version": _identifier(data, "rubric_version"), "label": data.get("label"),
        "score": _score(data, "score"), "confidence": _score(data, "confidence"),
        "annotator_id_hash": data.get("annotator_id_hash"), "review_timestamp": data.get("review_timestamp"),
        "sanitized_prompt": redact_text_for_artifact(str(data.get("sanitized_prompt") or "")),
        "sanitized_context": redact_text_for_artifact(str(data.get("sanitized_context") or "")),
        "sanitized_output": redact_text_for_artifact(str(data.get("sanitized_output") or "")),
        "notes": redact_text_for_artifact(str(data.get("notes") or "")),
        "adjudication_status": str(data.get("adjudication_status") or "pending"),
        "evidence_references": redact_for_artifact(dict(data.get("evidence_references") or {})),
        "status": status,
    }
    if not out["example_id"] and not out["episode_id"]:
        raise ReviewValidationError("example_id or episode_id is required")
    if out["adjudication_status"] not in _ADJUDICATION_STATUSES:
        raise ReviewValidationError(f"invalid adjudication_status: {out['adjudication_status']!r}")
    if status == "completed":
        label = str(out["label"] or "").strip().lower()
        if label not in LABELS_BY_DIMENSION[dimension]:
            raise ReviewValidationError(f"invalid label {label!r} for {dimension}")
        if require_completed:
            if not out["annotator_id_hash"] or not re.fullmatch(r"[0-9a-fA-F]{8,128}", str(out["annotator_id_hash"])):
                raise ReviewValidationError("completed annotations require an 8-128 character hexadecimal annotator_id_hash")
            timestamp = str(out["review_timestamp"] or "")
            try:
                datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ReviewValidationError("completed annotations require an ISO-8601 review_timestamp") from exc
            if out["confidence"] is None:
                raise ReviewValidationError("completed annotations require confidence")
            if not any(out[key] for key in ("sanitized_prompt", "sanitized_context", "sanitized_output")):
                raise ReviewValidationError("completed annotations require sanitized review content or evidence references")
            evidence_mode = (out["evidence_references"] or {}).get("evidence_mode")
            if str(evidence_mode or "").upper() not in EVIDENCE_MODES:
                raise ReviewValidationError("completed annotations require a valid evidence_references.evidence_mode")
    elif require_completed:
        raise ReviewValidationError("annotation is not completed")
    return redact_for_artifact(out)


__all__ = [
    "LABELS_BY_DIMENSION", "REVIEW_DIMENSIONS", "ReviewValidationError",
    "normalize_dimension", "validate_annotation",
]
