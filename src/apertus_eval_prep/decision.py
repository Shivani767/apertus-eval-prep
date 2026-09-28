"""Decision stability: does the *selection* survive configuration changes?

Three distinct questions, deliberately kept separate in this platform:

* score stability    -- does the measured score move?          (``stability.py``)
* ranking stability  -- does the model ordering move?           (``ranking.py``)
* decision stability -- does the *chosen option* move?          (this module)

A ranking can churn while the selected model never changes, and a ranking can
look stable while the decision flips because the winner moved inside the noise
band. Only the third question is about the thing an engineer actually acts on,
so it gets its own measurement instead of being inferred from the other two.

Selection itself is NOT reimplemented here. A decision is produced by
``metrics.pareto.select_configurations`` / ``pareto_frontier``, which already
implement explicit constraint directions, per-point rejection reasons, and
``insufficient_evidence`` handling where a missing objective is never read as a
zero. This module adds only the layer the platform was missing: apply one
declared policy across many evaluation configurations and measure how often the
outcome is the same decision.

Guarantees
----------
* The decision policy is data, never code: objectives (with direction) plus
  constraints. Nothing about "the baseline decision" is hard-coded.
* A missing objective yields ``insufficient_evidence``, never a score of 0, and
  such a configuration is reported as excluded rather than counted as a reversal.
* Ties are a first-class outcome, not silently rounded into a win or a loss.
* Reversal "causes" are associations with the configuration factors that differ
  from the baseline configuration. Under one-factor-at-a-time designs the
  attribution is a single changed factor; where several factors differ the
  record is explicitly marked confounded. Nothing here claims causality.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from apertus_eval_prep.core.evidence import normalize_evidence
# ``_point_value`` is imported rather than re-derived so objective aliasing
# (``quality`` -> ``quality_score`` -> ``task_score``) is defined in exactly one
# place; ``interaction.py`` already reuses ``sweep._base_cell`` the same way.
from apertus_eval_prep.metrics.pareto import _point_value, select_configurations

#: Schema tag written into every decision artifact.
DECISION_SCHEMA_VERSION = "1.0"

#: Same discipline as ``release.gates.RELEASE_GATE_DISCLAIMER``: this is a policy
#: aid, not an approval, and it must survive into every report surface.
DECISION_STABILITY_DISCLAIMER = (
    "Decision-stability results describe how a declared selection policy behaves "
    "across evaluated configurations. They are engineering policy aids and are "
    "not production approval, model certification, or a causal explanation."
)

#: Outcome of applying a policy to one configuration.
OUTCOME_SAME = "same_decision"
OUTCOME_TIE_WITH_BASELINE = "tie_includes_baseline"
OUTCOME_REVERSAL = "decision_reversal"
OUTCOME_NO_DECISION = "no_eligible_option"
OUTCOME_INVALID = "invalid_configuration"

#: Outcomes that count toward the denominator of ``decision_stability``.
_DETERMINABLE_OUTCOMES = (
    OUTCOME_SAME,
    OUTCOME_TIE_WITH_BASELINE,
    OUTCOME_REVERSAL,
    OUTCOME_NO_DECISION,
)

_VALID_DIRECTIONS = ("min", "max")


class DecisionPolicyError(ValueError):
    """Raised when a declared decision policy is unusable or ambiguous."""


def _number(value: Any) -> float | None:
    """Finite-number coercion; bools are rejected so flags never become scores."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _label_of(point: Mapping[str, Any]) -> str:
    """Same identity precedence as ``metrics.pareto._label``."""
    return str(
        point.get("label")
        or point.get("configuration_id")
        or point.get("run_id")
        or "<unnamed>"
    )


@dataclass(frozen=True)
class DecisionPolicy:
    """A declared, auditable selection policy.

    ``objectives`` maps an objective name to ``"min"`` or ``"max"``.
    ``constraints`` uses the constraint language already supported by
    ``select_configurations``: a bare key is a minimum, ``max_<field>`` an upper
    bound, or the explicit ``{"field": ..., "op": "min"|"max", "value": ...}``
    form. Direction is always explicit so a policy file can never silently flip
    the meaning of a latency ceiling.
    """

    name: str = "declared_policy"
    objectives: dict[str, str] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.objectives:
            raise DecisionPolicyError(
                "a decision policy needs at least one objective; without an "
                "objective direction there is no defined winner"
            )
        for name, direction in self.objectives.items():
            if direction not in _VALID_DIRECTIONS:
                raise DecisionPolicyError(
                    f"objective {name!r} has direction {direction!r}; "
                    f"expected one of {_VALID_DIRECTIONS}"
                )
        if not isinstance(self.constraints, dict):
            raise DecisionPolicyError("constraints must be a mapping")

    @property
    def primary_objective(self) -> str:
        """The declared tie-break objective (declaration order, like a policy)."""
        return next(iter(self.objectives))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "objectives": dict(self.objectives),
            "constraints": dict(self.constraints),
            "notes": list(self.notes),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "DecisionPolicy":
        """Parse a policy block. ``objectives`` accepts a mapping or a list."""
        if not isinstance(data, Mapping):
            raise DecisionPolicyError("decision policy must be a mapping")
        raw = data.get("objectives") or {}
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            # ``objectives: [quality, latency]`` -- direction still has to be
            # declared explicitly, so a bare list pairs with
            # ``objective_direction: {quality: max, latency: min}``.
            directions = data.get("objective_direction") or {}
            objectives = {str(k): str(directions.get(k, "max")) for k in raw}
        elif isinstance(raw, Mapping):
            objectives = {str(k): str(v) for k, v in raw.items()}
        else:
            raise DecisionPolicyError("objectives must be a mapping or a sequence")
        return cls(
            name=str(data.get("name") or "declared_policy"),
            objectives=objectives,
            constraints=dict(data.get("constraints") or {}),
            notes=tuple(str(n) for n in (data.get("notes") or ())),
        )


def decide(points: Sequence[Mapping[str, Any]], policy: DecisionPolicy) -> dict[str, Any]:
    """Apply one policy to the candidate options of a single configuration.

    Resolution order, recorded explicitly so a reader can see *how* a decision
    was reached and not merely that one appeared:

    1. constraint filtering (``select_configurations``);
    2. if exactly one option survives, that is the decision;
    3. otherwise the Pareto frontier of the eligible set is taken;
    4. exactly one frontier member -> decision;
    5. several frontier members -> ``tie`` (never an arbitrary pick).

    Returns ``decision=None`` with an explanatory ``resolution`` whenever a
    single choice is not supported by the evidence.
    """
    materialised = [dict(point) for point in points]
    if not materialised:
        return {
            "decision": None,
            "resolution": "no_options",
            "reason": "configuration contributed no candidate options",
            "tied": [],
            "violations": [],
            "n_options": 0,
            "n_eligible": 0,
            "insufficient_evidence": True,
        }

    selection = select_configurations(
        materialised, policy.constraints, objectives=policy.objectives
    )
    eligible = list(selection.get("eligible") or [])
    rejected = list(selection.get("rejected") or [])
    frontier = list(selection.get("pareto_optimal") or [])

    violations = [
        {"option": _label_of(item), "reasons": list(item.get("rejection_reasons") or [])}
        for item in rejected
    ]

    selected_point: Mapping[str, Any] | None = None
    if len(eligible) == 1:
        selected_point = eligible[0]
        decision, resolution, reason = _label_of(selected_point), "unique_eligible", (
            "exactly one option satisfied every declared constraint"
        )
    elif not eligible:
        if selection.get("insufficient_evidence"):
            decision, resolution = None, "insufficient_evidence"
            # Distinct wording from a genuine constraint failure: nothing was
            # rejected for being bad, it could not be evaluated at all.
            reason = (
                "no option could be evaluated: at least one objective was never "
                "measured, so it is unknown rather than zero"
            )
        else:
            decision, resolution, reason = None, "no_eligible", (
                "no option met the declared constraints on available evidence"
            )
    elif len(frontier) == 1:
        selected_point = frontier[0]
        decision, resolution, reason = _label_of(selected_point), "pareto_unique", (
            f"{len(eligible)} options were eligible; exactly one is "
            f"non-dominated on {sorted(policy.objectives)}"
        )
    else:
        decision, resolution, reason = None, "tie", (
            f"{len(frontier)} eligible options are mutually non-dominated on "
            f"{sorted(policy.objectives)}; the policy does not break this tie"
        )

    return {
        "decision": decision,
        "resolution": resolution,
        "reason": reason,
        "tied": [_label_of(item) for item in frontier] if resolution == "tie" else [],
        # The measured objective values behind the decision, so a reader can
        # check the selection without re-running the policy. ``None`` rather
        # than 0 whenever an objective was not measured.
        "selected_objectives": (
            {k: _number(_objective(selected_point, k)) for k in policy.objectives}
            if selected_point is not None
            else None
        ),
        "violations": violations,
        "eligible": [_label_of(item) for item in eligible],
        "n_options": len(materialised),
        "n_eligible": len(eligible),
        "insufficient_evidence": bool(selection.get("insufficient_evidence")),
        "policy_status": selection.get("status"),
    }


def _objective(point: Mapping[str, Any], field_name: str) -> Any:
    """Read an objective value, honouring the alias table used by selection."""
    return _point_value(point, field_name)


def _classify(
    outcome: dict[str, Any], baseline_decision: str | None
) -> tuple[str, str]:
    """Map one configuration's decision to a stability outcome class.

    Kept as a pure function so the classification rules are unit-testable in
    isolation and cannot drift between callers.
    """
    decision = outcome.get("decision")
    resolution = outcome.get("resolution")
    if resolution in ("no_options", "insufficient_evidence"):
        return OUTCOME_INVALID, str(outcome.get("reason") or "insufficient evidence")
    if decision is not None:
        if decision == baseline_decision:
            return OUTCOME_SAME, "selected the baseline decision"
        return OUTCOME_REVERSAL, f"selected {decision!r} instead of {baseline_decision!r}"
    if resolution == "tie":
        tied = outcome.get("tied") or []
        if baseline_decision in tied:
            return (
                OUTCOME_TIE_WITH_BASELINE,
                "baseline decision tied for best; not counted as a reversal",
            )
        return OUTCOME_REVERSAL, (
            f"baseline decision {baseline_decision!r} absent from the tie set {tied}"
        )
    if resolution == "no_eligible":
        return OUTCOME_NO_DECISION, "no option met the declared constraints"
    return OUTCOME_INVALID, f"unresolved decision state: {resolution!r}"


def decision_stability(
    configurations: Sequence[Mapping[str, Any]],
    policy: DecisionPolicy,
    *,
    baseline_config: str | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Measure whether a declared policy reaches the same decision throughout.

    ``configurations`` is a sequence of evaluated configurations, each::

        {"configuration_id": "backend=vllm",
         "factors": {"backend": "vllm", "prompt": "baseline"},
         "points": [{"label": "model_a", "quality": 0.71, ...}, ...]}

    ``factors`` is optional; when present it drives the reversal-cause
    breakdown, which is an association with the factors that differ from the
    baseline configuration and never a causal claim.

    Denominator rule (stated because it decides the headline number): a
    configuration counts as *valid* when the policy produced a determinable
    outcome -- a unique decision, a tie set, or a deliberate "nothing is
    eligible". A configuration where an objective was never measured is
    ``invalid_configuration``, is excluded from the denominator, and is listed
    with its reason. Missing evidence never becomes a reversal and never
    becomes a zero.
    """
    configs = [dict(config) for config in configurations]
    if not configs:
        return {
            "metric": "decision_stability",
            "schema_version": DECISION_SCHEMA_VERSION,
            "status": "insufficient_design",
            "reason": "no configurations supplied; stability is undefined",
            "policy": policy.to_dict(),
            "stability": None,
            "valid_configurations": 0,
            "disclaimer": DECISION_STABILITY_DISCLAIMER,
            "evidence": normalize_evidence(evidence),
        }

    ids = [str(c.get("configuration_id") or f"config_{index}") for index, c in enumerate(configs)]
    if len(set(ids)) != len(ids):
        raise DecisionPolicyError("configuration_id values must be unique")

    if baseline_config is None:
        baseline_index = 0
    else:
        if baseline_config not in ids:
            raise DecisionPolicyError(
                f"baseline_config {baseline_config!r} is not among the evaluated configurations"
            )
        baseline_index = ids.index(baseline_config)
    baseline_id = ids[baseline_index]

    evaluated: list[dict[str, Any]] = []
    for config_id, config in zip(ids, configs):
        points = list(config.get("points") or [])
        record: dict[str, Any] = {
            "configuration_id": config_id,
            "factors": dict(config.get("factors") or {}),
            "is_baseline": config_id == baseline_id,
            "n_options": len(points),
        }
        try:
            outcome = decide(points, policy)
        except DecisionPolicyError as exc:  # malformed constraint/objective data
            outcome = {
                "decision": None,
                "resolution": "no_options",
                "reason": f"policy could not be applied: {exc}",
                "tied": [],
                "violations": [],
            }
        record.update(outcome)
        evaluated.append(record)

    baseline = evaluated[baseline_index]
    baseline_decision = baseline.get("decision")

    if baseline_decision is None:
        # Without a baseline decision there is nothing to be stable *against*.
        # Reporting a stability number here would be meaningless, so the
        # artifact declines instead.
        return {
            "metric": "decision_stability",
            "schema_version": DECISION_SCHEMA_VERSION,
            "status": "insufficient_design",
            "reason": (
                f"baseline configuration {baseline_id!r} produced no decision "
                f"({baseline.get('resolution')}: {baseline.get('reason')}); "
                "stability relative to a non-decision is undefined"
            ),
            "policy": policy.to_dict(),
            "baseline_config": baseline_id,
            "baseline_decision": None,
            "configurations": evaluated,
            "stability": None,
            "valid_configurations": 0,
            "disclaimer": DECISION_STABILITY_DISCLAIMER,
            "evidence": normalize_evidence(evidence),
        }

    baseline_factors = baseline.get("factors") or {}
    counts = {outcome: 0 for outcome in _DETERMINABLE_OUTCOMES}
    counts[OUTCOME_INVALID] = 0
    cause_counts: dict[str, int] = {}
    cause_attribution: dict[str, str] = {}
    reversal_records: list[dict[str, Any]] = []

    for record in evaluated:
        if record["is_baseline"]:
            record["outcome"] = "baseline"
            record["outcome_reason"] = "reference configuration for this comparison"
            continue
        outcome, reason = _classify(record, baseline_decision)
        record["outcome"] = outcome
        record["outcome_reason"] = reason
        counts[outcome] += 1
        if outcome != OUTCOME_REVERSAL:
            continue

        factors = record.get("factors") or {}
        # A factor counts as *changed* only when both configurations declare it
        # and the levels differ. A key present on one side only is a difference
        # in metadata completeness, not evidence that the factor was perturbed;
        # treating it as a change would label every OFAT cell that omits the
        # baseline's other keys as confounded.
        both = set(factors) & set(baseline_factors)
        changed = sorted(
            name for name in both if factors.get(name) != baseline_factors.get(name)
        )
        undeclared = sorted((set(factors) ^ set(baseline_factors)))
        if not changed:
            attribution = "unknown"
        elif len(changed) > 1:
            attribution = "multi_factor_confounded"
        elif undeclared:
            attribution = "single_factor_incomplete_metadata"
        else:
            attribution = "single_factor"
        for name in changed:
            cause_counts[name] = cause_counts.get(name, 0) + 1
            cause_attribution[name] = attribution
        reversal_records.append(
            {
                "configuration_id": record["configuration_id"],
                "selected": record.get("decision"),
                "changed_factors": {name: baseline_factors.get(name) for name in changed},
                "changed_factors_to": {name: factors.get(name) for name in changed},
                "undeclared_factors": undeclared,
                "attribution_quality": attribution,
                "reason": reason,
            }
        )

    valid = sum(counts[outcome] for outcome in _DETERMINABLE_OUTCOMES)
    same = counts[OUTCOME_SAME]
    ties_with_baseline = counts[OUTCOME_TIE_WITH_BASELINE]
    reversal_factors = sorted(
        ({"factor": name, "reversals": count} for name, count in cause_counts.items()),
        key=lambda item: (-item["reversals"], item["factor"]),
    )
    for entry in reversal_factors:
        entry["causal_claim"] = False
        entry["attribution_quality"] = cause_attribution[entry["factor"]]

    single_family = [
        r for r in reversal_records if str(r["attribution_quality"]).startswith("single_factor")
    ]
    confounded = [
        r for r in reversal_records if r["attribution_quality"] == "multi_factor_confounded"
    ]
    if not reversal_records:
        design = "insufficient_metadata"
    elif len(single_family) == len(reversal_records):
        design = "single_factor"
    elif single_family and confounded:
        design = "mixed"
    elif confounded:
        design = "confounded"
    else:
        design = "insufficient_metadata"

    return {
        "metric": "decision_stability",
        "schema_version": DECISION_SCHEMA_VERSION,
        "status": "ok" if valid else "insufficient_design",
        "policy": policy.to_dict(),
        "policy_name": policy.name,
        "baseline_config": baseline_id,
        "baseline_decision": baseline_decision,
        "baseline_resolution": baseline.get("resolution"),
        "baseline_reason": baseline.get("reason"),
        "n_configurations": len(evaluated),
        "valid_configurations": valid,
        "same_decision": same,
        "stability": round(same / valid, 6) if valid else None,
        "decision_reversals": counts[OUTCOME_REVERSAL],
        "tie_with_baseline": ties_with_baseline,
        "no_decision_configurations": counts[OUTCOME_NO_DECISION],
        "invalid_configurations": counts[OUTCOME_INVALID],
        # Reported separately and never merged into `stability`: a tie that still
        # contains the baseline decision is weaker than a unique repeat but is
        # not a reversal. Readers choose the definition, seeing both.
        "stability_allowing_ties": (
            round((same + ties_with_baseline) / valid, 6) if valid else None
        ),
        "denominator_rule": (
            "valid_configurations counts configurations where the policy produced a "
            "determinable outcome (unique decision, tie set, or a deliberate "
            "no-eligible result); invalid configurations are excluded and listed"
        ),
        "outcome_counts": dict(counts),
        "reversal_causes": reversal_factors,
        "reversal_cause_design": design,
        "reversals": reversal_records,
        "excluded_configurations": [
            {
                "configuration_id": record["configuration_id"],
                "reason": record.get("outcome_reason") or record.get("reason"),
            }
            for record in evaluated
            if not record["is_baseline"] and record["outcome"] == OUTCOME_INVALID
        ],
        "configurations": evaluated,
        "interpretation": (
            f"Across {valid} valid configuration(s) the policy selected "
            f"{baseline_decision!r} in {same}; a different option in "
            f"{counts[OUTCOME_REVERSAL]}; tied while still containing it in "
            f"{ties_with_baseline}; and found nothing eligible in "
            f"{counts[OUTCOME_NO_DECISION]}."
        ),
        "disclaimer": DECISION_STABILITY_DISCLAIMER,
        "evidence": normalize_evidence(evidence),
    }


__all__ = [
    "DECISION_SCHEMA_VERSION",
    "DECISION_STABILITY_DISCLAIMER",
    "DecisionPolicy",
    "DecisionPolicyError",
    "decide",
    "decision_stability",
]
