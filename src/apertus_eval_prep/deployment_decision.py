"""Four-objective deployment decisions: quality x latency x cost x memory.

Adds memory as a first-class decision input alongside the existing quality,
latency and cost objectives. Memory is unusual in one respect that drives the
whole design: it is a **capacity ceiling**, not a soft trade-off. Two options
that both fit in 24 GB are equally acceptable on memory; one needing 40 GB is
simply not deployable, regardless of its accuracy.

The trap this module avoids: memory is frequently **never measured** in an
evaluation run. A deployment point with no memory reading must not be treated as
using 0 GB, or it passes every memory constraint and looks optimal. An
unmeasured objective yields `insufficient_evidence`, the point is excluded from
the frontier, and the artifact discloses how much of the decision rested on
complete information.

Selection is delegated to `metrics.pareto`, so constraint semantics stay in one
place. This module supplies the policy, the memory objective, and the disclosure.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from apertus_eval_prep.core.evidence import normalize_evidence
from apertus_eval_prep.metrics.pareto import pareto_frontier, select_configurations

DEPLOYMENT_DECISION_SCHEMA_VERSION = "1.0"

DEPLOYMENT_DECISION_DISCLAIMER = (
    "Deployment decision results state which options satisfied a declared policy "
    "on the objectives that were actually measured. They are an engineering "
    "selection aid, not a production approval, a capacity guarantee, or evidence "
    "that the selected option is the best available."
)

#: Direction of each supported objective. Quality is a floor to clear; the rest
#: are ceilings to stay under.
DECISION_OBJECTIVES: dict[str, str] = {
    "quality": "max",
    "latency_p95_ms": "min",
    "cost": "min",
    "memory_gb": "min",
}

#: Objectives whose absence makes a decision materially incomplete. Memory is
#: first because it is the most commonly unmeasured of the four, and the most
#: likely to invalidate a selection if silently assumed to be zero.
DECISIVE_OBJECTIVES: tuple[str, ...] = (
    "memory_gb", "latency_p95_ms", "cost", "quality",
)

_OBJECTIVE_ALIASES: dict[str, tuple[str, ...]] = {
    "memory_gb": ("memory_gb", "memory", "peak_memory_gb"),
    "latency_p95_ms": ("latency_p95_ms", "p95_latency_ms", "p95_ms"),
    "quality": ("quality", "quality_score", "task_score"),
    "cost": ("cost", "cost_per_success", "cost_value"),
}


class DeploymentPolicyError(ValueError):
    """Raised when a declared deployment policy cannot be applied."""


def _objective_value(point: Mapping[str, Any], key: str) -> float | None:
    """Read an objective honouring aliases. Returns None when unmeasured."""
    for candidate in _OBJECTIVE_ALIASES.get(key, (key,)):
        value = point.get(candidate)
        if value is None or isinstance(value, bool):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _name(point: Mapping[str, Any]) -> str:
    return str(point.get("label") or point.get("configuration_id") or "<unnamed>")


def analyse_deployment_decision(
    points: Sequence[Mapping[str, Any]],
    *,
    constraints: Mapping[str, Any] | None = None,
    objectives: Mapping[str, str] | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Decide among deployment options over quality, latency, cost and memory.

    Reports three things usually conflated: the frontier among options whose
    every objective was measured; the selection satisfying the declared
    constraints; and the completeness of the decision -- which decisive
    objectives were never measured, and so how far the selection can be trusted.

    A point missing any declared objective is excluded from the frontier and
    cannot be selected. It is never treated as scoring zero on that objective.
    """
    declared = dict(objectives or DECISION_OBJECTIVES)
    for name, direction in declared.items():
        if direction not in ("min", "max"):
            raise DeploymentPolicyError(
                f"objective {name!r} has direction {direction!r}; expected min or max"
            )

    materialised = [dict(point) for point in points]
    coverage = {
        name: {
            "measured": sum(1 for p in materialised
                            if _objective_value(p, name) is not None),
            "unmeasured": sum(1 for p in materialised
                              if _objective_value(p, name) is None),
        }
        for name in declared
    }
    complete = [
        p for p in materialised
        if all(_objective_value(p, name) is not None for name in declared)
    ]
    incomplete = [
        {
            "label": _name(p),
            "missing_objectives": [
                name for name in declared if _objective_value(p, name) is None
            ],
        }
        for p in materialised
        if any(_objective_value(p, name) is None for name in declared)
    ]

    frontier = pareto_frontier(complete, declared)
    result: dict[str, Any] = {
        "metric": "deployment_decision_analysis",
        "schema_version": DEPLOYMENT_DECISION_SCHEMA_VERSION,
        "n_points": len(materialised),
        "n_complete": len(complete),
        "n_incomplete": len(incomplete),
        "objectives": declared,
        "objective_coverage": coverage,
        "frontier": [_name(p) for p in frontier["frontier"]],
        "dominated": [_name(p) for p in frontier["dominated"]],
        "excluded_for_unmeasured_objectives": incomplete,
        "decision": None,
        "selection_status": "NO_CONSTRAINTS",
    }
    if constraints:
        selection = select_configurations(complete, dict(constraints), objectives=declared)
        result["selection_status"] = selection["status"]
        result["decision"] = (
            _name(selection["recommendation"]) if selection.get("recommendation") else None
        )
        result["eligible"] = [_name(p) for p in selection["eligible"]]
        result["rejections"] = [
            {"label": _name(p), "reasons": list(p.get("rejection_reasons") or [])}
            for p in selection["rejected"]
        ]
        result["insufficient_evidence"] = bool(selection.get("insufficient_evidence"))

    unmeasured_decisive = [
        name for name in DECISIVE_OBJECTIVES
        if name in declared and coverage[name]["unmeasured"] > 0
    ]
    result["decision_completeness"] = "complete" if not unmeasured_decisive else "partial"
    result["unmeasured_decisive_objectives"] = unmeasured_decisive
    result["limits"] = [
        "A point missing any declared objective is excluded rather than scored "
        "zero; an unmeasured memory figure must not be read as 0 GB.",
        "A partial decision_completeness means the selection was reached with at "
        "least one decisive objective unmeasured for some options.",
        "Frontier membership is non-dominance on the declared objectives among "
        "options that were actually measured, not a quality judgement.",
    ]
    result["disclaimer"] = DEPLOYMENT_DECISION_DISCLAIMER
    result["evidence"] = normalize_evidence(evidence)
    return result


__all__ = [
    "DECISION_OBJECTIVES",
    "DECISIVE_OBJECTIVES",
    "DEPLOYMENT_DECISION_DISCLAIMER",
    "DEPLOYMENT_DECISION_SCHEMA_VERSION",
    "DeploymentPolicyError",
    "analyse_deployment_decision",
]