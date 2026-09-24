"""Structured, sanitized failure records and deterministic investigation profiles.

The profile summarizes observed patterns only. It does not infer causes from
correlations, and it never turns missing denominators into measured zeroes.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping

from apertus_eval_prep.utils.pii import redact_for_artifact, sanitize_for_report

FAILURE_RECORD_VERSION = "1.0"
FAILURE_CATEGORIES: tuple[str, ...] = (
    "incorrect_answer", "unsupported_claim", "invalid_citation",
    "prompt_sensitive_failure", "backend_sensitive_failure",
    "quantization_sensitive_failure", "long_context_failure",
    "retrieval_distractor_failure", "contradictory_context_failure",
    "tool_schema_failure", "tool_sequence_failure", "tool_recovery_failure",
    "unsafe_completion", "false_refusal", "privacy_sensitive_output",
    "timeout", "infrastructure_error", "unknown",
)
FAILURE_RECORD_FIELDS: tuple[str, ...] = (
    "schema_version", "failure_id", "run_id", "parent_experiment_id",
    "example_id", "episode_id", "test_id", "task", "domain", "language", "locale",
    "category", "taxonomy_category", "subcategory", "failure_type", "severity", "timestamp",
    "model_id", "model_revision", "backend", "device", "precision", "quantization",
    "prompt_hash", "config_hash", "input_hash", "sanitized_input_excerpt",
    "sanitized_output_excerpt", "source_reference", "tool_trace_reference",
    "condition_labels", "reproduction_command", "run_reference", "error",
    "evaluated", "human_review_status", "tags",
)
_SAFETY_CATEGORIES = {
    "prompt_injection": "unsafe_completion",
    "data_leakage": "privacy_sensitive_output",
    "unauthorized_instruction_override": "unsafe_completion",
    "unsafe_tool_use": "unsafe_completion",
    "harmful_content_compliance": "unsafe_completion",
    "benign_false_refusal": "false_refusal",
    "privacy_sensitive_output": "privacy_sensitive_output",
    "unsupported_high_stakes_claim": "unsupported_claim",
    "misleading_confidence": "unsupported_claim",
    "policy_bypass_attempt": "unsafe_completion",
    "retrieval_context_manipulation": "retrieval_distractor_failure",
}
_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def _first(value: Any, fallback: Any = None) -> Any:
    return fallback if value is None or value == "" else value


def _canonical_type(record: Mapping[str, Any]) -> str:
    explicit = str(record.get("failure_type") or record.get("subcategory") or "").strip()
    if explicit in FAILURE_CATEGORIES:
        return explicit
    category = str(record.get("category") or "").strip()
    error = str(record.get("error") or "").lower()
    if category in _SAFETY_CATEGORIES:
        return _SAFETY_CATEGORIES[category]
    aliases = {
        "wrong_answer": "incorrect_answer", "unparseable": "unknown",
        "empty_output": "unknown", "runtime_error": "infrastructure_error",
        "infrastructure_failure": "infrastructure_error",
        "timeout_or_infrastructure_failure": "timeout" if "timeout" in error else "infrastructure_error",
        "episode_failure": "infrastructure_error" if "timeout" in error or "adapter" in error else "incorrect_answer",
    }
    return aliases.get(category, category if category in FAILURE_CATEGORIES else "unknown")


def normalize_failure_record(
    record: Mapping[str, Any], *, manifest: Mapping[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Return a versioned, safely sanitized failure record."""
    row = dict(record)
    model = dict(manifest.get("model") or {}) if manifest else {}
    backend = dict(manifest.get("backend") or {}) if manifest else {}
    row["schema_version"] = _first(row.get("schema_version"), FAILURE_RECORD_VERSION)
    identity = row.get("example_id") or row.get("episode_id") or row.get("test_id") or "unknown"
    row["failure_id"] = _first(row.get("failure_id"), f"{row.get('run_id', 'unknown')}:{identity}")
    row["run_id"] = _first(row.get("run_id"), manifest.get("run_id") if manifest else None)
    row["parent_experiment_id"] = _first(row.get("parent_experiment_id"), manifest.get("parent_experiment_id") if manifest else None)
    for field in FAILURE_RECORD_FIELDS:
        row.setdefault(field, None)
    row["category"] = _first(row.get("category"), "unknown")
    row["taxonomy_category"] = _first(row.get("taxonomy_category"), row.get("category"))
    row["failure_type"] = _canonical_type(row)
    row["subcategory"] = _first(row.get("subcategory"), row["failure_type"] if row["failure_type"] != "unknown" else None)
    row["condition_labels"] = list(dict.fromkeys(
        str(x) for x in (row.get("condition_labels") or row.get("conditions") or []) if x
    ))
    row["tags"] = list(dict.fromkeys(str(x) for x in (row.get("tags") or []) if x))
    row["model_id"] = _first(row.get("model_id"), model.get("model_id"))
    row["model_revision"] = _first(row.get("model_revision"), model.get("model_revision"))
    row["backend"] = _first(row.get("backend"), model.get("adapter_kind"))
    row["device"] = _first(row.get("device"), backend.get("device"))
    row["precision"] = _first(row.get("precision"), backend.get("precision"))
    row["quantization"] = _first(row.get("quantization"), backend.get("quantization"))
    row["config_hash"] = _first(row.get("config_hash"), manifest.get("config_hash") if manifest else None)
    row["prompt_hash"] = _first(row.get("prompt_hash"), (manifest.get("prompt") or {}).get("template_hash") if manifest else None)
    row["source_reference"] = _first(row.get("source_reference"), row.get("citation_reference"))
    row["tool_trace_reference"] = _first(row.get("tool_trace_reference"), row.get("trace_reference"))
    row["run_reference"] = _first(row.get("run_reference"), row.get("output_reference"))
    row["timestamp"] = _first(row.get("timestamp"), timestamp or (manifest.get("utc") if manifest else None))
    for field in ("sanitized_input_excerpt", "sanitized_output_excerpt", "error", "reproduction_command", "run_reference"):
        value = row.get(field)
        if value is not None and value != "":
            row[field] = sanitize_for_report(str(value), max_chars=400)
    # Keep the normalized schema extensible, but pass every persisted value through
    # the credential-safe artifact boundary before it can be written.
    return redact_for_artifact(row)


def normalize_failure_records(records: Iterable[Mapping[str, Any]], **context: Any) -> list[dict[str, Any]]:
    return [normalize_failure_record(row, **context) for row in records]



def _identity(row: Mapping[str, Any]) -> str:
    return str(row.get("example_id") or row.get("episode_id") or row.get("test_id") or row.get("failure_id") or "unknown")


def _rate(count: int, total: Any) -> float | None:
    try:
        denominator = float(total)
    except (TypeError, ValueError):
        return None
    return count / denominator if denominator > 0 else None


def _priority(row: Mapping[str, Any], *, failure_rate: float | None, baseline_delta: int | None = None) -> dict[str, Any]:
    severity = str(row.get("severity") or "medium").lower()
    category = str(row.get("category") or "unknown")
    safety = severity in {"high", "critical"} or category in _SAFETY_CATEGORIES
    sensitive = bool(row.get("condition_labels")) or row.get("failure_type") in {
        "prompt_sensitive_failure", "backend_sensitive_failure", "quantization_sensitive_failure",
    }
    score = _SEVERITY_RANK.get(severity, 2) * 10
    reasons = [f"severity={severity}"]
    if safety:
        score += 20
        reasons.append("safety-relevant category")
    if failure_rate is not None and failure_rate >= 0.2:
        score += 10
        reasons.append(f"observed failure rate={failure_rate:.4f}")
    if baseline_delta is not None and baseline_delta > 0:
        score += 15
        reasons.append(f"baseline delta={baseline_delta:+d}")
    if sensitive:
        score += 5
        reasons.append("condition-sensitive label observed")
    priority = "P0" if score >= 45 else "P1" if score >= 30 else "P2" if score >= 20 else "P3"
    return {"priority": priority, "score": score, "reasons": reasons, "observed_pattern": True}


def failure_fingerprint(
    failures: Iterable[Mapping[str, Any]], *, conditions: Mapping[str, Any] | None = None,
    total: int | None = None, baseline_fingerprint: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate failures into an auditable observed-pattern profile."""
    rows = normalize_failure_records(failures)
    categories = Counter(str(row.get("failure_type") or row.get("category") or "unknown") for row in rows)
    taxonomy_categories = Counter(str(row.get("category") or row.get("failure_type") or "unknown") for row in rows)
    types = Counter(str(row.get("failure_type") or "unknown") for row in rows)
    severities = Counter(str(row.get("severity") or "unknown").lower() for row in rows)
    total_value = total if total is not None else (conditions or {}).get("n_total")
    failure_rate = _rate(len(rows), total_value)
    by_example: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_example[_identity(row)].append(row)
    condition_sensitive: list[str] = []
    stable: list[str] = []
    for identity, items in sorted(by_example.items()):
        labels = sorted({str(label) for item in items for label in (item.get("condition_labels") or [])})
        run_count = len({str(item.get("run_id")) for item in items if item.get("run_id")})
        if labels or run_count > 1:
            condition_sensitive.append(identity)
        elif len(items) == 1:
            stable.append(identity)
    safety_rows = [row for row in rows if str(row.get("severity") or "").lower() in {"high", "critical"} or row.get("category") in _SAFETY_CATEGORIES]
    baseline_counts = dict((baseline_fingerprint or {}).get("by_category") or {})
    deltas = {category: count - int(baseline_counts.get(category, 0)) for category, count in sorted(categories.items())}
    comparison = {
        "status": "UNAVAILABLE",
        "reasons": ["no baseline failure fingerprint was supplied"],
        "category_deltas": None,
    }
    if baseline_fingerprint is not None:
        comparison = {
            "status": "OBSERVED_DELTA",
            "reasons": ["candidate minus baseline counts; correlation is not causation"],
            "category_deltas": deltas,
            "baseline_failure_count": baseline_fingerprint.get("n_failures"),
            "candidate_failure_count": len(rows),
        }
    priorities = []
    for row in rows:
        category = str(row.get("failure_type") or row.get("category") or "unknown")
        priorities.append({**_priority(row, failure_rate=failure_rate, baseline_delta=deltas.get(category, 0)), "category": category, "failure_id": row.get("failure_id")})
    priorities.sort(key=lambda item: (-item["score"], str(item.get("category")), str(item.get("failure_id"))))
    representatives = []
    ordered = sorted(rows, key=lambda item: (-_priority(item, failure_rate=failure_rate, baseline_delta=deltas.get(str(item.get("category") or "unknown"), 0))["score"], _identity(item)))
    for row in ordered[:10]:
        representatives.append({
            "failure_id": row.get("failure_id"), "example_id": row.get("example_id"),
            "episode_id": row.get("episode_id"), "test_id": row.get("test_id"),
            "category": row.get("failure_type") or row.get("category"),
            "taxonomy_category": row.get("category"),
            "failure_type": row.get("failure_type"),
            "severity": row.get("severity"), "sanitized_input_excerpt": row.get("sanitized_input_excerpt"),
            "sanitized_output_excerpt": row.get("sanitized_output_excerpt"),
            "condition_labels": list(row.get("condition_labels") or []),
            "tool_trace_reference": row.get("tool_trace_reference") or row.get("trace_reference"),
        })
    dominant = [[category, count] for category, count in categories.most_common(5)]
    old_priority = "safety" if safety_rows else ("stability" if condition_sensitive else ("quality" if rows else "none"))
    return {
        "schema_version": "1.0", "n_failures": len(rows), "n_total": total_value,
        "failure_rate": failure_rate, "by_category": dict(categories),
        "by_taxonomy_category": dict(taxonomy_categories),
        "by_failure_type": dict(types), "by_severity": dict(severities),
        "dominant_failure_modes": dominant, "top_failure_modes": dominant,
        "safety_critical_failures": len(safety_rows), "stable_failures": stable,
        "configuration_sensitive_examples": condition_sensitive,
        "condition_sensitive_failures": condition_sensitive,
        "investigation_priorities": priorities,
        "representative_sanitized_examples": representatives,
        "baseline_comparison": comparison,
        "recommended_investigation_priority": old_priority,
        "top_investigation_priority": priorities[0]["priority"] if priorities else None,
        "priority_rules": {
            "severity": "critical=4, high=3, medium=2, low=1; missing defaults to medium",
            "baseline_delta": "+15 score when candidate failure count exceeds baseline",
            "safety": "+20 for high/critical severity or safety taxonomy category",
            "failure_rate": "+10 when observed failure rate is at least 0.20",
            "condition_sensitivity": "+5 when a condition-sensitive label is present",
            "causality": "observed pattern only; no causal claim",
        },
        "conditions": dict(conditions or {}),
        "limitations": [
            "Failure categories and priorities are observed patterns, not causal conclusions.",
            "Baseline deltas require aligned comparison evidence.",
            "Representative excerpts are sanitized and truncated.",
        ],
    }


__all__ = [
    "FAILURE_RECORD_VERSION", "FAILURE_CATEGORIES", "FAILURE_RECORD_FIELDS",
    "normalize_failure_record", "normalize_failure_records", "failure_fingerprint",
]
