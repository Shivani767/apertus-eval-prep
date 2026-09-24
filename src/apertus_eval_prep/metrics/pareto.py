"""Multi-objective Pareto frontier and transparent dominance explanations."""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


_CONSTRAINT_ALIASES = {
    "quality": ("quality", "quality_score", "task_score"),
    "groundedness": ("groundedness", "groundedness_score"),
    "p95_latency_ms": ("latency_p95_ms", "p95_latency_ms", "p95_ms"),
    "p50_latency_ms": ("latency_p50_ms", "p50_latency_ms", "p50_ms"),
    "mean_latency_ms": ("latency_mean_ms", "mean_latency_ms", "mean_ms"),
    "cost": ("cost", "cost_per_success", "cost_value"),
    "cost_per_success": ("cost_per_success", "cost", "cost_value"),
    "latency_p95_ms": ("latency_p95_ms", "p95_latency_ms", "p95_ms"),
    "p95_latency_ms": ("latency_p95_ms", "p95_latency_ms", "p95_ms"),
    "latency_p50_ms": ("latency_p50_ms", "p50_latency_ms", "p50_ms"),
    "p50_latency_ms": ("latency_p50_ms", "p50_latency_ms", "p50_ms"),
    "latency_mean_ms": ("latency_mean_ms", "mean_latency_ms", "mean_ms"),
    "mean_latency_ms": ("latency_mean_ms", "mean_latency_ms", "mean_ms"),
    "variance": ("variance", "quality_variance"),
    "safety_score": ("safety_score", "safety"),
    "robustness_score": ("robustness_score", "robustness"),
}


def _point_value(point: Mapping[str, Any], field: str) -> Any:
    for candidate in _CONSTRAINT_ALIASES.get(field, (field,)):
        if candidate in point:
            return point[candidate]
    return None


def _label(point: Mapping[str, Any]) -> str:
    return str(point.get("label") or point.get("configuration_id") or point.get("run_id") or "<unnamed>")


def _objective_value(point: Mapping[str, Any], field: str) -> Any:
    return _point_value(point, field)


def _dominates(left: Mapping[str, Any], right: Mapping[str, Any], objectives: Mapping[str, str]) -> bool:
    at_least_as_good = True
    strictly_better = False
    for key, direction in objectives.items():
        if direction not in {"min", "max"}:
            raise ValueError(f"unsupported objective direction: {direction!r}")
        a, b = _number(_point_value(left, key)), _number(_point_value(right, key))
        if a is None or b is None:
            return False
        if direction == "min":
            at_least_as_good = at_least_as_good and a <= b
            strictly_better = strictly_better or a < b
        else:
            at_least_as_good = at_least_as_good and a >= b
            strictly_better = strictly_better or a > b
    return at_least_as_good and strictly_better


def pareto_frontier(
    points: Sequence[Mapping[str, Any]], objectives: Mapping[str, str]
) -> dict[str, Any]:
    """Return frontier, dominated, and excluded points with explanations."""
    usable: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for point in points:
        missing = [key for key in objectives if _number(_point_value(point, key)) is None]
        if missing:
            excluded.append({
                **dict(point), "pareto": "excluded",
                "reason": "missing or non-finite objective value",
                "missing_objectives": missing,
            })
        else:
            usable.append(dict(point))
    frontier: list[dict[str, Any]] = []
    dominated: list[dict[str, Any]] = []
    for point in usable:
        dominators = [other for other in usable if other is not point and _dominates(other, point, objectives)]
        if dominators:
            names = [_label(other) for other in dominators]
            dominated.append({
                **point, "pareto": "dominated", "dominated_by": names,
                "reason": f"dominated by {', '.join(names)}",
            })
        else:
            frontier.append({**point, "pareto": "frontier", "reason": "not dominated on configured objectives"})
    return {
        "frontier": frontier,
        "dominated": dominated,
        "excluded": excluded,
        "objectives": dict(objectives),
        "insufficient_evidence": bool(excluded),
    }


def select_configurations(
    points: Sequence[Mapping[str, Any]], constraints: Mapping[str, Any],
    *, objectives: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Filter configurations and explain every rejection reason.

    A scalar constraint is a minimum.  For upper bounds use ``max_<field>`` or
    ``{"field": {"op": "max", "value": 2.0}}``; this keeps constraints readable
    while making direction explicit in machine-readable configs.  When objectives
    are supplied, the result also identifies eligible Pareto-optimal options.
    """
    eligible: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    insufficient = False
    for point in points:
        reasons: list[str] = []
        for key, rule in constraints.items():
            mode = "min"
            field = key
            limit = rule
            label = key
            if key.startswith("max_"):
                field, mode, limit = key[4:], "max", rule
                label = key
            elif key.startswith("min_"):
                field, mode, limit = key[4:], "min", rule
                label = key
            if isinstance(rule, Mapping):
                field = str(rule.get("field", field))
                mode = str(rule.get("op", rule.get("mode", mode)))
                limit = rule.get("value", rule.get("limit"))
                label = str(rule.get("label", field))
            if mode not in {"min", "max"}:
                reasons.append(f"{label}: unsupported constraint direction {mode!r}")
                continue
            value = _number(_point_value(point, field))
            bound = _number(limit)
            if value is None:
                insufficient = True
                reasons.append(f"{field}: insufficient evidence")
                continue
            if bound is None:
                reasons.append(f"{field}: invalid constraint limit")
                continue
            passed = value >= bound if mode == "min" else value <= bound
            if not passed:
                word = "minimum" if mode == "min" else "maximum"
                reasons.append(f"{field}={value} violates {word} {bound}")
        item = {**dict(point), "eligible": not reasons, "rejection_reasons": reasons}
        (rejected if reasons else eligible).append(item)
    pareto_optimal: list[dict[str, Any]] = []
    if objectives:
        frontier = pareto_frontier(eligible, objectives)
        pareto_optimal = list(frontier["frontier"])
    status = (
        "INSUFFICIENT_EVIDENCE" if insufficient and not eligible
        else "UNIQUE_ELIGIBLE" if len(eligible) == 1
        else "NO_ELIGIBLE" if not eligible
        else "MULTIPLE_OPTIONS"
    )
    return {
        "eligible": eligible,
        "pareto_optimal": pareto_optimal,
        "rejected": rejected,
        "constraints": dict(constraints),
        "insufficient_evidence": insufficient,
        "recommendation": eligible[0] if len(eligible) == 1 else None,
        "recommendation_status": status,
        "status": status,
    }


__all__ = ["pareto_frontier", "select_configurations"]
