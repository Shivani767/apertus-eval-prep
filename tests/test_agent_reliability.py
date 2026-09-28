"""Agent reliability: coverage is not quality, and a missing metric is not a pass.

Two failure modes dominate here. A suite that declares eleven scenario classes,
runs them all and fails most of them must not report the same headline as one
that skips half the taxonomy -- so declared, executed and succeeded are counted
separately. And a metric the run never reported must never be able to satisfy a
regression gate, because a gate that passes on missing evidence is worse than
having no gate at all.
"""

from __future__ import annotations

import json

import pytest

from apertus_eval_prep.agent_reliability import (
    GATE_FAIL,
    GATE_INCONCLUSIVE,
    GATE_PASS,
    REGRESSION_GATE_DISCLAIMER,
    SCENARIO_CLASSES,
    AgentPolicyError,
    agent_metrics,
    compare_agent_runs,
    evaluate_regression_policy,
    scenario_coverage,
    validate_scenarios,
)

BASE_SYSTEM = {
    "episode_count": 10,
    "task_completion_rate": 0.90,
    "tool_sequence_validity": 1.0,
    "tool_schema_validity": 1.0,
    "groundedness_mean": 0.90,
    "recovery_success_rate": 1.0,
    "tool_call_efficiency": 1.0,
    "end_to_end_latency_ms_mean": 100.0,
    "unsafe_action_count": 0,
    "tool_call_count": 20,
    "input_tokens": 1000,
    "output_tokens": 500,
    "token_count": 1500,
}


def _variant(**changes):
    """Copy of the base system with keys removed when set to None."""
    system = dict(BASE_SYSTEM)
    for key, value in changes.items():
        if value is None:
            system.pop(key, None)
        else:
            system[key] = value
    return system


class TestAgentMetrics:
    def test_metrics_map_onto_named_agent_concepts(self):
        metrics = agent_metrics(BASE_SYSTEM)
        assert metrics["task_success"] == 0.90
        assert metrics["tool_selection"] == 1.0
        assert metrics["tool_argument_correctness"] == 1.0
        assert metrics["groundedness"] == 0.90
        assert metrics["latency_ms_mean"] == 100.0

    def test_totals_are_converted_to_per_episode_means(self):
        metrics = agent_metrics(BASE_SYSTEM)
        assert metrics["input_tokens_mean"] == 100.0
        assert metrics["output_tokens_mean"] == 50.0
        assert metrics["total_tokens_mean"] == 150.0
        assert metrics["tool_calls_mean"] == 2.0

    def test_missing_metrics_are_none_never_zero(self):
        metrics = agent_metrics(_variant(groundedness_mean=None, recovery_success_rate=None))
        assert metrics["groundedness"] is None
        assert metrics["recovery"] is None

    def test_unsafe_action_rate_uses_the_episode_denominator(self):
        assert agent_metrics(_variant(unsafe_action_count=2))["unsafe_action_rate"] == 0.2

    def test_empty_system_yields_all_none(self):
        metrics = agent_metrics({})
        assert metrics["task_success"] is None
        assert metrics["episode_count"] is None

    def test_zero_episode_count_does_not_divide_by_zero(self):
        metrics = agent_metrics(_variant(episode_count=0, unsafe_action_count=0))
        assert metrics["unsafe_action_rate"] is None


class TestScenarioValidation:
    def test_every_taxonomy_class_is_accepted(self):
        declared = [
            {"scenario_id": f"s{i}", "scenario_class": name, "applies": True}
            for i, name in enumerate(SCENARIO_CLASSES)
        ]
        assert len(validate_scenarios(declared)) == len(SCENARIO_CLASSES)

    def test_unknown_class_is_rejected(self):
        with pytest.raises(AgentPolicyError, match="unknown scenario_class"):
            validate_scenarios([{"scenario_id": "s1", "scenario_class": "vibes", "applies": True}])

    def test_applicability_must_be_declared(self):
        with pytest.raises(AgentPolicyError, match="applies"):
            validate_scenarios([{"scenario_id": "s1", "scenario_class": "happy_path"}])

    def test_duplicate_ids_are_rejected(self):
        entry = {"scenario_id": "s1", "scenario_class": "happy_path", "applies": True}
        with pytest.raises(AgentPolicyError, match="duplicate"):
            validate_scenarios([entry, dict(entry)])

    def test_missing_id_is_rejected(self):
        with pytest.raises(AgentPolicyError, match="scenario_id"):
            validate_scenarios([{"scenario_class": "happy_path", "applies": True}])


class TestScenarioCoverage:
    DECLARED = [
        {"scenario_id": "s1", "scenario_class": "happy_path", "applies": True},
        {"scenario_id": "s2", "scenario_class": "tool_failure", "applies": True},
        {"scenario_id": "s3", "scenario_class": "policy_boundary", "applies": True},
        {"scenario_id": "s4", "scenario_class": "long_context", "applies": False},
    ]

    def test_declared_executed_and_succeeded_are_separate_numbers(self):
        result = scenario_coverage(self.DECLARED, [
            {"scenario_id": "s1", "executed": True, "succeeded": True},
            {"scenario_id": "s2", "executed": True, "succeeded": False},
            {"scenario_id": "s3", "executed": False, "succeeded": None},
        ])
        assert result["declared_scenarios"] == 3
        assert result["executed_scenarios"] == 2
        assert result["succeeded_scenarios"] == 1
        assert result["failed_scenarios"] == 1
        assert result["untested_scenarios"] == ["s3"]

    def test_not_applicable_is_excluded_from_the_denominator(self):
        result = scenario_coverage(self.DECLARED, [
            {"scenario_id": "s1", "executed": True, "succeeded": True},
        ])
        assert result["declared_scenarios"] == 3
        assert result["not_applicable_scenarios"] == 1
        assert "s4" not in result["untested_scenarios"]

    def test_full_execution_coverage_with_failures_is_still_low_quality(self):
        # The exact confusion this module exists to prevent.
        result = scenario_coverage(self.DECLARED, [
            {"scenario_id": "s1", "executed": True, "succeeded": False},
            {"scenario_id": "s2", "executed": True, "succeeded": False},
            {"scenario_id": "s3", "executed": True, "succeeded": True},
        ])
        assert result["execution_coverage"] == 1.0
        assert result["success_rate_of_executed"] == pytest.approx(1 / 3)

    def test_untested_declared_scenarios_are_named(self):
        result = scenario_coverage(self.DECLARED, [])
        assert result["execution_coverage"] == 0.0
        assert set(result["untested_scenarios"]) == {"s1", "s2", "s3"}
        assert result["success_rate_of_executed"] is None

    def test_executed_without_signal_is_not_counted_as_success(self):
        result = scenario_coverage(self.DECLARED, [
            {"scenario_id": "s1", "executed": True, "succeeded": None},
        ])
        assert result["executed_without_signal"] == 1
        assert result["succeeded_scenarios"] == 0
        assert result["success_rate_of_executed"] is None

    def test_coverage_is_not_quality_is_stated(self):
        result = scenario_coverage(self.DECLARED, [])
        assert any("Coverage is not quality" in limit for limit in result["limits"])

    def test_taxonomy_size_is_reported(self):
        assert scenario_coverage(self.DECLARED, [])["taxonomy_size"] == len(SCENARIO_CLASSES)


class TestRegressionComparison:
    def test_improvement_and_regression_are_distinguished(self):
        comparison = compare_agent_runs(
            BASE_SYSTEM,
            _variant(task_completion_rate=0.93, tool_sequence_validity=0.96),
        )
        assert comparison["metrics"]["task_success"]["status"] == "improved"
        assert comparison["metrics"]["tool_selection"]["status"] == "regressed"
        assert comparison["regressions"] == ["tool_selection"]

    def test_no_change_is_reported_as_unchanged(self):
        comparison = compare_agent_runs(BASE_SYSTEM, BASE_SYSTEM)
        assert all(m["status"] == "unchanged" for m in comparison["metrics"].values())
        assert comparison["regressions"] == []

    def test_latency_increase_is_a_regression_due_to_direction(self):
        # A higher latency is worse even though the raw delta is positive.
        comparison = compare_agent_runs(BASE_SYSTEM, _variant(end_to_end_latency_ms_mean=115.0))
        assert comparison["metrics"]["latency_ms_mean"]["direction"] == "lower_is_better"
        assert comparison["metrics"]["latency_ms_mean"]["status"] == "regressed"

    def test_latency_decrease_is_an_improvement(self):
        comparison = compare_agent_runs(BASE_SYSTEM, _variant(end_to_end_latency_ms_mean=80.0))
        assert comparison["metrics"]["latency_ms_mean"]["status"] == "improved"

    def test_missing_metric_is_not_comparable_never_zero(self):
        comparison = compare_agent_runs(BASE_SYSTEM, _variant(groundedness_mean=None))
        entry = comparison["metrics"]["groundedness"]
        assert entry["status"] == "not_comparable"
        assert entry["delta"] is None
        assert "groundedness" in comparison["not_comparable"]
        assert "groundedness" not in comparison["regressions"]

    def test_unsafe_action_increase_is_a_regression(self):
        comparison = compare_agent_runs(BASE_SYSTEM, _variant(unsafe_action_count=1))
        assert comparison["metrics"]["unsafe_action_rate"]["status"] == "regressed"

    def test_run_ids_are_carried_through(self):
        comparison = compare_agent_runs(
            BASE_SYSTEM, BASE_SYSTEM, baseline_id="agent-v1", candidate_id="agent-v2"
        )
        assert comparison["baseline"] == "agent-v1"
        assert comparison["candidate"] == "agent-v2"


POLICY = {
    "task_success": {"minimum_delta": -0.02},
    "tool_selection": {"minimum_delta": -0.02},
    "groundedness": {"minimum_delta": -0.02},
    "latency_ms_mean": {"maximum_relative_increase": 0.20},
}


class TestRegressionGate:
    def test_clean_improvement_passes(self):
        comparison = compare_agent_runs(
            BASE_SYSTEM,
            _variant(task_completion_rate=0.93, tool_sequence_validity=1.0,
                     groundedness_mean=0.92, end_to_end_latency_ms_mean=100.0),
        )
        gate = evaluate_regression_policy(comparison, POLICY)
        assert gate["status"] == GATE_PASS
        assert gate["n_failed"] == 0

    def test_regression_beyond_tolerance_fails(self):
        comparison = compare_agent_runs(BASE_SYSTEM, _variant(tool_sequence_validity=0.90))
        gate = evaluate_regression_policy(comparison, POLICY)
        assert gate["status"] == GATE_FAIL
        failed = [g for g in gate["gates"] if g["verdict"] == GATE_FAIL]
        assert failed[0]["metric"] == "tool_selection"
        assert "worse than allowed" in failed[0]["reason"]

    def test_missing_metric_is_inconclusive_and_never_passes(self):
        comparison = compare_agent_runs(BASE_SYSTEM, _variant(groundedness_mean=None))
        gate = evaluate_regression_policy(comparison, POLICY)
        verdicts = {g["metric"]: g["verdict"] for g in gate["gates"]}
        assert verdicts["groundedness"] == GATE_INCONCLUSIVE
        assert gate["n_inconclusive"] == 1

    def test_breach_outranks_inconclusive_in_the_overall_status(self):
        comparison = compare_agent_runs(
            BASE_SYSTEM,
            _variant(tool_sequence_validity=0.90, groundedness_mean=None),
        )
        gate = evaluate_regression_policy(comparison, POLICY)
        # A measured breach is a FAIL even though another metric is unknown:
        # the breach is a fact, the missing metric is only a gap.
        assert gate["status"] == GATE_FAIL

    def test_relative_increase_within_budget_passes(self):
        # 100 -> 115 is +15%, inside a 20% budget.
        comparison = compare_agent_runs(BASE_SYSTEM, _variant(end_to_end_latency_ms_mean=115.0))
        gate = evaluate_regression_policy(comparison, POLICY)
        entry = [g for g in gate["gates"] if g["metric"] == "latency_ms_mean"][0]
        assert entry["verdict"] == GATE_PASS
        assert entry["relative_change"] == pytest.approx(0.15)

    def test_relative_increase_beyond_budget_fails(self):
        # 100 -> 130 is +30%, beyond the 20% budget.
        comparison = compare_agent_runs(BASE_SYSTEM, _variant(end_to_end_latency_ms_mean=130.0))
        gate = evaluate_regression_policy(comparison, POLICY)
        entry = [g for g in gate["gates"] if g["metric"] == "latency_ms_mean"][0]
        assert entry["verdict"] == GATE_FAIL
        assert "exceeds" in entry["reason"]

    def test_empty_policy_is_inconclusive_not_pass(self):
        gate = evaluate_regression_policy(compare_agent_runs(BASE_SYSTEM, BASE_SYSTEM), {})
        assert gate["status"] == GATE_INCONCLUSIVE

    def test_gating_an_unknown_metric_is_rejected(self):
        comparison = compare_agent_runs(BASE_SYSTEM, BASE_SYSTEM)
        with pytest.raises(AgentPolicyError, match="not one of the compared metrics"):
            evaluate_regression_policy(comparison, {"vibes": {"minimum_delta": 0}})

    def test_rule_without_a_threshold_is_rejected(self):
        comparison = compare_agent_runs(BASE_SYSTEM, BASE_SYSTEM)
        with pytest.raises(AgentPolicyError, match="minimum_delta"):
            evaluate_regression_policy(comparison, {"task_success": {}})

    def test_result_is_labelled_a_policy_gate_result(self):
        gate = evaluate_regression_policy(compare_agent_runs(BASE_SYSTEM, BASE_SYSTEM), POLICY)
        assert gate["result_type"] == "policy gate result"
        assert gate["disclaimer"] == REGRESSION_GATE_DISCLAIMER
        assert "not production approval" in gate["disclaimer"]

    def test_status_meaning_is_defined_for_every_verdict(self):
        gate = evaluate_regression_policy(compare_agent_runs(BASE_SYSTEM, BASE_SYSTEM), POLICY)
        for verdict in (GATE_PASS, GATE_FAIL, GATE_INCONCLUSIVE):
            assert verdict in gate["status_meaning"]

    def test_evidence_mode_is_preserved(self):
        gate = evaluate_regression_policy(
            compare_agent_runs(BASE_SYSTEM, BASE_SYSTEM), POLICY, evidence={"mode": "MOCK"}
        )
        assert gate["evidence"]["mode"] == "MOCK"
        assert gate["evidence"]["real_model_execution"] is False

    def test_gate_is_json_safe_and_deterministic(self):
        first = evaluate_regression_policy(
            compare_agent_runs(BASE_SYSTEM, _variant(task_completion_rate=0.93)), POLICY
        )
        second = evaluate_regression_policy(
            compare_agent_runs(BASE_SYSTEM, _variant(task_completion_rate=0.93)), POLICY
        )
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
        assert json.loads(json.dumps(first)) == first
