"""Agent reliability: scenario coverage, regression comparison, policy gates.

Episode execution already exists (``core/episode_runner.py``,
``tasks/agent_episode.py``, ``evaluators/tool_use.py``). What is missing is the
layer that turns a set of finished episodes into the three questions a team
actually asks about an agent change:

1. **What was tested?** Scenario coverage, with an explicit split between a
   scenario being *declared*, being *executed*, and *succeeding*. Collapsing
   those into one "coverage" number would let a suite that runs everything and
   fails everything look identical to one that skips half the taxonomy.
2. **Did the change regress anything?** A baseline/candidate comparison over
   named metrics with the deltas and the regression list kept visible.
3. **Does the declared policy accept it?** A gate whose verdict is explicitly a
   *policy gate result*, never an approval.

Two rules run through all of it:

* A metric that was not measured is ``None``, never ``0``. An absent metric must
  not be able to satisfy a gate, and must not look like a successful zero.
* Coverage is not quality. Nothing here converts "we tested 11 scenario classes"
  into "the agent is reliable".
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from apertus_eval_prep.core.evidence import normalize_evidence

AGENT_SCHEMA_VERSION = "1.0"

REGRESSION_GATE_DISCLAIMER = (
    "Regression-gate results are engineering policy aids: they state whether a "
    "candidate meets a declared comparison policy against a baseline on the "
    "evaluated episodes. They are not production approval, not a safety "
    "certification, and not evidence that the agent is safe in general."
)

#: Scenario classes an agent suite may declare. Not every class applies to
#: every agent, so applicability is declared per scenario rather than assumed;
#: a class that does not apply is reported as declared-not-applicable instead of
#: silently counting as an untested gap.
SCENARIO_CLASSES: tuple[str, ...] = (
    "happy_path",
    "ambiguous_request",
    "missing_information",
    "tool_failure",
    "malformed_tool_output",
    "conflicting_information",
    "long_context",
    "repeated_request",
    "adversarial_input",
    "policy_boundary",
    "recovery",
)

#: Metrics compared between a baseline and a candidate agent run.
AGENT_METRICS: tuple[str, ...] = (
    "task_success",
    "tool_selection",
    "tool_argument_correctness",
    "groundedness",
    "recovery",
    "tool_call_efficiency",
    "latency_ms_mean",
    "input_tokens_mean",
    "output_tokens_mean",
    "total_tokens_mean",
    "unsafe_action_rate",
)

#: Metrics where a *lower* value is better. Everything else is higher-is-better.
#: ``unsafe_action_rate`` belongs here: more unsafe actions must never be scored
#: as an improvement just because the raw delta is positive.
LOWER_IS_BETTER: frozenset[str] = frozenset(
    {
        "latency_ms_mean",
        "input_tokens_mean",
        "output_tokens_mean",
        "total_tokens_mean",
        "unsafe_action_rate",
    }
)


class AgentPolicyError(ValueError):
    """Raised when a declared scenario or regression policy is unusable."""


def _number(value: Any) -> float | None:
    """Finite-number coercion that never turns a missing value into 0."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def agent_metrics(system: Mapping[str, Any] | None) -> dict[str, Any]:
    """Normalise an episode run's ``system`` block into named agent metrics.

    Reads the already-emitted metrics of a finished run; it measures nothing.
    Every metric is ``None`` when the run did not report it -- notably
    ``recovery`` is ``None`` when no tool ever failed, because "no failure was
    observed" is not "recovery was perfect".
    """
    block = dict(system or {})
    episode_count = _number(block.get("episode_count"))
    unsafe_actions = _number(block.get("unsafe_action_count"))

    def _per_episode(total: Any) -> float | None:
        value = _number(total)
        if value is None or not episode_count:
            return None
        return value / episode_count

    return {
        "task_success": _number(block.get("task_completion_rate")),
        "tool_selection": _number(block.get("tool_sequence_validity")),
        "tool_argument_correctness": _number(block.get("tool_schema_validity")),
        "groundedness": _number(block.get("groundedness_mean")),
        "groundedness_citation_coverage": _number(block.get("source_citation_coverage")),
        "recovery": _number(block.get("recovery_success_rate")),
        "tool_call_efficiency": _number(block.get("tool_call_efficiency")),
        "unsafe_action_rate": (
            None if unsafe_actions is None or not episode_count
            else unsafe_actions / episode_count
        ),
        "latency_ms_mean": _number(block.get("end_to_end_latency_ms_mean")),
        "tool_calls_mean": _per_episode(block.get("tool_call_count")),
        "input_tokens_mean": _per_episode(block.get("input_tokens")),
        "output_tokens_mean": _per_episode(block.get("output_tokens")),
        "total_tokens_mean": _per_episode(block.get("token_count")),
        "episode_count": episode_count,
        "retrieval_failure_count": _number(block.get("retrieval_failure_count")),
        "unsupported_claim_rate": _number(block.get("unsupported_claim_rate")),
    }


def validate_scenarios(scenarios: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate declared scenarios, preserving declaration order.

    ``applies`` is explicit. A class the agent genuinely does not face is
    marked not-applicable instead of being left to look like a coverage gap.
    """
    validated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in scenarios:
        scenario = dict(raw)
        scenario_id = str(scenario.get("scenario_id") or "").strip()
        if not scenario_id:
            raise AgentPolicyError("every scenario needs a non-empty scenario_id")
        if scenario_id in seen:
            raise AgentPolicyError(f"duplicate scenario_id: {scenario_id!r}")
        seen.add(scenario_id)
        scenario_class = str(scenario.get("scenario_class") or "").strip()
        if scenario_class not in SCENARIO_CLASSES:
            raise AgentPolicyError(
                f"unknown scenario_class {scenario_class!r} for {scenario_id!r}; "
                f"expected one of {SCENARIO_CLASSES}"
            )
        applies = scenario.get("applies")
        if applies is None:
            raise AgentPolicyError(
                f"scenario {scenario_id!r} must declare applies=true or applies=false"
            )
        validated.append({
            "scenario_id": scenario_id,
            "scenario_class": scenario_class,
            "applies": bool(applies),
            "notes": str(scenario.get("notes") or ""),
        })
    return validated


def scenario_coverage(
    declared: Sequence[Mapping[str, Any]],
    outcomes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Report scenario coverage with declaration, execution and success apart.

    The three readings answer different questions and are never merged:

    * **count coverage** -- how much of the applicable taxonomy was declared;
    * **execution coverage** -- how much of what was declared actually ran;
    * **successful outcome** -- of what ran, how much succeeded.

    Collapsing them would let a suite that runs every scenario and fails most
    of them report the same headline as one that skips half the taxonomy.
    Coverage is not quality, and the artifact says so.

    ``outcomes`` entries are ``{scenario_id, executed, succeeded}``; ``executed``
    false means the scenario never ran, and ``succeeded`` ``None`` means it ran
    but produced no pass/fail signal.
    """
    scenarios = validate_scenarios(declared)
    applicable = [s for s in scenarios if s["applies"]]
    not_applicable = [s for s in scenarios if not s["applies"]]

    by_id = {str(o.get("scenario_id")): dict(o) for o in outcomes}
    executed_ids, succeeded_ids, failed_ids, no_signal_ids = [], [], [], []
    for scenario in applicable:
        outcome = by_id.get(scenario["scenario_id"])
        if outcome is None or not bool(outcome.get("executed")):
            continue
        executed_ids.append(scenario["scenario_id"])
        succeeded = outcome.get("succeeded")
        if succeeded is None:
            no_signal_ids.append(scenario["scenario_id"])
        elif bool(succeeded):
            succeeded_ids.append(scenario["scenario_id"])
        else:
            failed_ids.append(scenario["scenario_id"])

    untested = [s["scenario_id"] for s in applicable
                if s["scenario_id"] not in executed_ids]
    declared_classes = {s["scenario_class"] for s in applicable}
    tested_classes = {
        s["scenario_class"] for s in applicable if s["scenario_id"] in executed_ids
    }
    n_applicable = len(applicable)
    denominator = len(succeeded_ids) + len(failed_ids)
    return {
        "metric": "scenario_coverage",
        "schema_version": AGENT_SCHEMA_VERSION,
        "taxonomy_size": len(SCENARIO_CLASSES),
        "declared_scenarios": n_applicable,
        "not_applicable_scenarios": len(not_applicable),
        "executed_scenarios": len(executed_ids),
        "succeeded_scenarios": len(succeeded_ids),
        "failed_scenarios": len(failed_ids),
        "executed_without_signal": len(no_signal_ids),
        "untested_scenarios": untested,
        "failed_scenario_ids": failed_ids,
        "count_coverage": (
            len(declared_classes) / len(SCENARIO_CLASSES) if SCENARIO_CLASSES else None
        ),
        "execution_coverage": (len(executed_ids) / n_applicable) if n_applicable else None,
        "success_rate_of_executed": (
            len(succeeded_ids) / denominator if denominator else None
        ),
        "applicable_class_coverage": (
            len(tested_classes) / len(declared_classes) if declared_classes else None
        ),
        "definitions": {
            "count_coverage": "applicable scenario classes declared / taxonomy size",
            "execution_coverage": "declared applicable scenarios executed / declared applicable",
            "success_rate_of_executed": "succeeded / (succeeded + failed) among executed",
        },
        "limits": [
            "Coverage is not quality: a suite can have full execution coverage "
            "and a low success rate.",
            "Scenarios marked applies=false are excluded from the denominators "
            "rather than counted as untested gaps.",
        ],
        "scenarios": scenarios,
    }


def compare_agent_runs(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    baseline_id: str = "baseline",
    candidate_id: str = "candidate",
) -> dict[str, Any]:
    """Compare a candidate agent run against a baseline, per named metric.

    Direction is respected: for a lower-is-better metric such as latency a
    decrease is an improvement, so ``improved``/``regressed`` are decided
    against the metric's own direction rather than the sign of the raw delta. A
    metric missing from either side is ``not_comparable``, never a delta of zero.
    """
    base = agent_metrics(baseline)
    cand = agent_metrics(candidate)
    metrics: dict[str, Any] = {}
    regressions: list[str] = []
    improvements: list[str] = []
    not_comparable: list[str] = []

    for name in AGENT_METRICS:
        base_value, cand_value = _number(base.get(name)), _number(cand.get(name))
        direction = "lower_is_better" if name in LOWER_IS_BETTER else "higher_is_better"
        if base_value is None or cand_value is None:
            metrics[name] = {
                "baseline": base_value,
                "candidate": cand_value,
                "delta": None,
                "direction": direction,
                "status": "not_comparable",
                "reason": "metric not reported by "
                          + ("the baseline" if base_value is None else "the candidate"),
            }
            not_comparable.append(name)
            continue
        delta = round(cand_value - base_value, 6)
        improved = delta < 0 if name in LOWER_IS_BETTER else delta > 0
        status = "unchanged" if delta == 0 else ("improved" if improved else "regressed")
        metrics[name] = {
            "baseline": base_value,
            "candidate": cand_value,
            "delta": delta,
            "direction": direction,
            "status": status,
        }
        if status == "regressed":
            regressions.append(name)
        elif status == "improved":
            improvements.append(name)

    return {
        "metric": "agent_regression_comparison",
        "schema_version": AGENT_SCHEMA_VERSION,
        "baseline": baseline_id,
        "candidate": candidate_id,
        "metrics": metrics,
        "regressions": regressions,
        "improvements": improvements,
        "not_comparable": not_comparable,
        "n_metrics_compared": len(AGENT_METRICS) - len(not_comparable),
        "limits": [
            "A delta between two runs over the same scenarios does not establish "
            "that the candidate is better in general.",
            "Metrics absent from either run are not_comparable, never zero.",
        ],
    }


#: Gate verdicts. ``INCONCLUSIVE`` is first-class: a policy cannot be satisfied
#: by a metric that was never measured.
GATE_PASS = "PASS"
GATE_FAIL = "FAIL"
GATE_INCONCLUSIVE = "INCONCLUSIVE"


def evaluate_regression_policy(
    comparison: Mapping[str, Any],
    policy: Mapping[str, Any],
    *,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply a declared regression policy to a baseline/candidate comparison.

    Policy shape (thresholds in data, never in code)::

        regression_policy:
          task_success:
            minimum_delta: -0.02
          latency_ms_mean:
            maximum_relative_increase: 0.20

    ``minimum_delta`` is the worst acceptable *signed change*, following the raw
    delta, so a latency drop is negative and clears a negative threshold.
    ``maximum_relative_increase`` compares candidate to baseline as a ratio and
    suits a cost or latency budget.

    A gated metric that is ``not_comparable`` yields ``INCONCLUSIVE`` rather than
    ``PASS``: an unmeasured metric must not be able to satisfy a gate. The
    overall status is ``INCONCLUSIVE`` when any gated metric is, and ``FAIL``
    only when a measured metric actually violates its threshold -- a missing
    metric is an evidence gap, not a breach.
    """
    metrics = dict(comparison.get("metrics") or {})
    results: list[dict[str, Any]] = []

    for name, rule in dict(policy or {}).items():
        if name not in metrics:
            raise AgentPolicyError(
                f"regression policy gates {name!r}, which is not one of the "
                f"compared metrics: {sorted(AGENT_METRICS)}"
            )
        entry = dict(metrics[name])
        threshold = dict(rule or {})
        if entry.get("status") == "not_comparable" or entry.get("delta") is None:
            results.append({
                "metric": name,
                "verdict": GATE_INCONCLUSIVE,
                "baseline": entry.get("baseline"),
                "candidate": entry.get("candidate"),
                "rule": threshold,
                "reason": entry.get("reason") or "metric was not compared",
            })
            continue
        delta = float(entry["delta"])
        baseline_value = float(entry["baseline"])
        if "minimum_delta" in threshold:
            allowed = float(threshold["minimum_delta"])
            passed = delta >= allowed
            results.append({
                "metric": name,
                "verdict": GATE_PASS if passed else GATE_FAIL,
                "observed_delta": delta,
                "allowed_delta": allowed,
                "rule": threshold,
                "reason": None if passed else f"delta {delta} is worse than allowed {allowed}",
            })
        elif "maximum_relative_increase" in threshold:
            limit = float(threshold["maximum_relative_increase"])
            if baseline_value == 0:
                results.append({
                    "metric": name,
                    "verdict": GATE_INCONCLUSIVE,
                    "observed_delta": delta,
                    "rule": threshold,
                    "reason": "baseline is zero, so a relative increase is undefined",
                })
                continue
            relative = (float(entry["candidate"]) - baseline_value) / abs(baseline_value)
            passed = relative <= limit
            results.append({
                "metric": name,
                "verdict": GATE_PASS if passed else GATE_FAIL,
                "relative_change": round(relative, 6),
                "allowed_relative_change": limit,
                "rule": threshold,
                "reason": None if passed else f"relative change {relative} exceeds {limit}",
            })
        else:
            raise AgentPolicyError(
                f"regression policy for {name!r} must declare minimum_delta or "
                f"maximum_relative_increase; got {sorted(threshold)}"
            )

    verdicts = [r["verdict"] for r in results]
    if not results:
        status = GATE_INCONCLUSIVE
    elif GATE_FAIL in verdicts:
        status = GATE_FAIL
    elif GATE_INCONCLUSIVE in verdicts:
        status = GATE_INCONCLUSIVE
    else:
        status = GATE_PASS

    return {
        "metric": "agent_regression_gate",
        "schema_version": AGENT_SCHEMA_VERSION,
        "result_type": "policy gate result",
        "status": status,
        "baseline": comparison.get("baseline"),
        "candidate": comparison.get("candidate"),
        "gates": results,
        "n_passed": sum(1 for r in results if r["verdict"] == GATE_PASS),
        "n_failed": sum(1 for r in results if r["verdict"] == GATE_FAIL),
        "n_inconclusive": sum(1 for r in results if r["verdict"] == GATE_INCONCLUSIVE),
        "unmeasured_metrics": list(comparison.get("not_comparable") or []),
        "regressions": list(comparison.get("regressions") or []),
        "status_meaning": {
            GATE_PASS: "every gated metric met its declared threshold",
            GATE_FAIL: "at least one measured metric violated its declared threshold",
            GATE_INCONCLUSIVE: "a gated metric could not be evaluated, because it "
                               "was not reported by both runs, or because the "
                               "declared rule is undefined for its value",
        },
        "disclaimer": REGRESSION_GATE_DISCLAIMER,
        "evidence": normalize_evidence(evidence),
    }


__all__ = [
    "AGENT_METRICS",
    "AGENT_SCHEMA_VERSION",
    "GATE_FAIL",
    "GATE_INCONCLUSIVE",
    "GATE_PASS",
    "LOWER_IS_BETTER",
    "REGRESSION_GATE_DISCLAIMER",
    "SCENARIO_CLASSES",
    "AgentPolicyError",
    "agent_metrics",
    "compare_agent_runs",
    "evaluate_regression_policy",
    "scenario_coverage",
    "validate_scenarios",
]

