"""Decision stability must be auditable, not just computable.

The number is the easy part. What is pinned here is the set of ways it can be
wrong: counting missing evidence as a reversal, quietly promoting a tie to a
win, reporting a stability figure when the baseline never decided anything, or
attributing a reversal to a factor the design cannot support. Each of those
turns a measured property into a fabricated one, which is the specific failure
mode this platform exists to prevent.
"""

from __future__ import annotations

import json

import pytest

from apertus_eval_prep.decision import (
    DECISION_STABILITY_DISCLAIMER,
    OUTCOME_INVALID,
    OUTCOME_NO_DECISION,
    OUTCOME_REVERSAL,
    OUTCOME_SAME,
    OUTCOME_TIE_WITH_BASELINE,
    DecisionPolicy,
    DecisionPolicyError,
    _classify,
    decide,
    decision_stability,
)

POLICY = DecisionPolicy.from_mapping(
    {
        "name": "quality_gate",
        "objectives": {"quality": "max", "cost": "min"},
        "constraints": {"quality": 0.60, "max_cost": 0.02},
    }
)


def _config(configuration_id, model_a, model_b, **factors):
    # The default mirrors a complete OFAT baseline: every factor is declared, so
    # a perturbed cell differs from it in exactly the key under test.
    return {
        "configuration_id": configuration_id,
        "factors": factors or {"backend": "transformers", "prompt": "baseline"},
        "points": [
            {"label": "model_a", "quality": model_a[0], "cost": model_a[1]},
            {"label": "model_b", "quality": model_b[0], "cost": model_b[1]},
        ],
    }


BASELINE = _config("baseline", (0.72, 0.005), (0.65, 0.010))
SAME = _config("fewshot", (0.70, 0.005), (0.66, 0.010), backend="transformers", prompt="fewshot")
# model_b becomes both more accurate and cheaper: genuine dominance, not a tie.
REVERSED = _config("vllm", (0.61, 0.010), (0.74, 0.005), backend="vllm", prompt="baseline")


class TestPolicyValidation:
    def test_policy_requires_an_objective(self):
        with pytest.raises(DecisionPolicyError, match="at least one objective"):
            DecisionPolicy.from_mapping({"constraints": {"quality": 0.5}})

    def test_objective_direction_must_be_explicit(self):
        with pytest.raises(DecisionPolicyError, match="direction"):
            DecisionPolicy.from_mapping({"objectives": {"quality": "higher"}})

    def test_objective_list_form_pairs_with_declared_direction(self):
        policy = DecisionPolicy.from_mapping(
            {"objectives": ["quality", "cost"], "objective_direction": {"cost": "min"}}
        )
        assert policy.objectives == {"quality": "max", "cost": "min"}
        assert policy.primary_objective == "quality"

    def test_non_mapping_policy_rejected(self):
        with pytest.raises(DecisionPolicyError):
            DecisionPolicy.from_mapping(["quality"])


class TestSingleDecision:
    def test_unique_winner_is_recorded_with_its_objective_values(self):
        outcome = decide(BASELINE["points"], POLICY)
        assert outcome["decision"] == "model_a"
        assert outcome["resolution"] == "pareto_unique"
        assert outcome["selected_objectives"] == {"quality": 0.72, "cost": 0.005}

    def test_tradeoff_is_a_tie_not_an_arbitrary_winner(self):
        # model_b is more accurate, model_a is cheaper: neither dominates, so
        # inventing a winner here would be an unsupported claim.
        tradeoff = _config("tradeoff", (0.72, 0.005), (0.80, 0.010))
        outcome = decide(tradeoff["points"], POLICY)
        assert outcome["decision"] is None
        assert outcome["resolution"] == "tie"
        assert sorted(outcome["tied"]) == ["model_a", "model_b"]

    def test_constraint_violation_is_reported_with_its_reason(self):
        failing = {
            "configuration_id": "slow",
            "points": [
                {"label": "model_a", "quality": 0.90, "cost": 0.50},
                {"label": "model_b", "quality": 0.65, "cost": 0.005},
            ],
        }
        outcome = decide(failing["points"], POLICY)
        assert outcome["decision"] == "model_b"
        reasons = outcome["violations"][0]["reasons"]
        assert any("cost" in reason and "maximum" in reason for reason in reasons)

    def test_no_eligible_option_is_distinct_from_missing_evidence(self):
        failing = {
            "configuration_id": "all_weak",
            "points": [
                {"label": "model_a", "quality": 0.10, "cost": 0.005},
                {"label": "model_b", "quality": 0.20, "cost": 0.006},
            ],
        }
        outcome = decide(failing["points"], POLICY)
        assert outcome["decision"] is None
        assert outcome["resolution"] == "no_eligible"
        assert outcome["insufficient_evidence"] is False

    def test_missing_objective_is_never_read_as_zero(self):
        # A cost of 0 would pass max_cost and quietly win on the min-cost
        # objective. Unmeasured cost must fail the objective, not fake it.
        unmeasured = {
            "configuration_id": "no_cost",
            "points": [
                {"label": "model_a", "quality": 0.90},
                {"label": "model_b", "quality": 0.70},
            ],
        }
        outcome = decide(unmeasured["points"], POLICY)
        assert outcome["decision"] is None
        assert outcome["resolution"] == "insufficient_evidence"
        assert outcome["insufficient_evidence"] is True

    def test_boolean_is_not_accepted_as_an_objective_value(self):
        points = [{"label": "model_a", "quality": True, "cost": 0.005}]
        assert decide(points, POLICY)["insufficient_evidence"] is True

    def test_empty_option_list_is_handled(self):
        outcome = decide([], POLICY)
        assert outcome["decision"] is None
        assert outcome["resolution"] == "no_options"


class TestStability:
    def test_identical_decisions_give_full_stability(self):
        result = decision_stability([BASELINE, SAME], POLICY)
        assert result["status"] == "ok"
        assert result["baseline_decision"] == "model_a"
        assert result["same_decision"] == 1
        assert result["stability"] == 1.0
        assert result["decision_reversals"] == 0
        assert result["valid_configurations"] == 1

    def test_reversal_is_detected_and_attributed_to_one_factor(self):
        result = decision_stability([BASELINE, REVERSED], POLICY)
        assert result["stability"] == 0.0
        assert result["decision_reversals"] == 1
        assert result["reversal_causes"] == [
            {
                "factor": "backend",
                "reversals": 1,
                "causal_claim": False,
                "attribution_quality": "single_factor",
            }
        ]

    def test_reversal_never_claims_causality(self):
        result = decision_stability([BASELINE, REVERSED], POLICY)
        assert all(entry["causal_claim"] is False for entry in result["reversal_causes"])

    def test_multi_factor_change_is_marked_confounded(self):
        confounded = _config(
            "both", (0.61, 0.010), (0.74, 0.005), backend="vllm", prompt="fewshot"
        )
        result = decision_stability([BASELINE, confounded], POLICY)
        assert result["reversal_cause_design"] == "confounded"
        assert {e["attribution_quality"] for e in result["reversal_causes"]} == {
            "multi_factor_confounded"
        }

    def test_undeclared_factor_keys_are_not_counted_as_changes(self):
        # An OFAT cell that omits the baseline's other keys has not perturbed
        # them; treating the omission as a change would call it confounded.
        partial = {
            "configuration_id": "partial",
            "factors": {"backend": "transformers", "quantization": "int4"},
            "points": [
                {"label": "model_a", "quality": 0.61, "cost": 0.010},
                {"label": "model_b", "quality": 0.74, "cost": 0.005},
            ],
        }
        result = decision_stability([BASELINE, partial], POLICY)
        record = result["reversals"][0]
        assert record["changed_factors"] == {}
        assert record["undeclared_factors"] == ["prompt", "quantization"]
        assert record["attribution_quality"] == "unknown"
        # Nothing is attributed when nothing can be localised.
        assert result["reversal_causes"] == []

    def test_fully_declared_single_change_is_single_factor(self):
        declared = {
            "configuration_id": "declared",
            "factors": {"backend": "vllm", "prompt": "baseline"},
            "points": [
                {"label": "model_a", "quality": 0.61, "cost": 0.010},
                {"label": "model_b", "quality": 0.74, "cost": 0.005},
            ],
        }
        result = decision_stability([BASELINE, declared], POLICY)
        assert result["reversals"][0]["attribution_quality"] == "single_factor"
        assert result["reversals"][0]["changed_factors"] == {"backend": "transformers"}
        assert result["reversals"][0]["changed_factors_to"] == {"backend": "vllm"}
        assert result["reversals"][0]["undeclared_factors"] == []

    def test_tie_containing_baseline_is_not_counted_as_reversal(self):
        tradeoff = _config("tradeoff", (0.72, 0.005), (0.80, 0.010), backend="vllm")
        result = decision_stability([BASELINE, tradeoff], POLICY)
        assert result["decision_reversals"] == 0
        assert result["tie_with_baseline"] == 1
        assert result["same_decision"] == 0
        # The two readings stay separate so neither is imposed on the reader.
        assert result["stability"] == 0.0
        assert result["stability_allowing_ties"] == 1.0

    def test_no_eligible_option_counts_as_a_determinable_outcome(self):
        all_weak = {
            "configuration_id": "all_weak",
            "factors": {"backend": "vllm"},
            "points": [
                {"label": "model_a", "quality": 0.10, "cost": 0.005},
                {"label": "model_b", "quality": 0.20, "cost": 0.006},
            ],
        }
        result = decision_stability([BASELINE, all_weak], POLICY)
        assert result["no_decision_configurations"] == 1
        assert result["valid_configurations"] == 1
        assert result["same_decision"] == 0

    def test_missing_metric_configuration_is_excluded_not_counted_as_reversal(self):
        unmeasured = {
            "configuration_id": "no_cost_measured",
            "factors": {"backend": "quantized"},
            "points": [{"label": "model_a", "quality": 0.90}, {"label": "model_b", "quality": 0.70}],
        }
        result = decision_stability([BASELINE, SAME, unmeasured], POLICY)
        assert result["invalid_configurations"] == 1
        assert result["decision_reversals"] == 0
        assert result["valid_configurations"] == 1
        assert result["same_decision"] == 1
        assert result["stability"] == 1.0
        assert [e["configuration_id"] for e in result["excluded_configurations"]] == [
            "no_cost_measured"
        ]
        assert "never measured" in result["excluded_configurations"][0]["reason"]

    def test_empty_configurations_report_insufficient_design(self):
        result = decision_stability([], POLICY)
        assert result["status"] == "insufficient_design"
        assert result["stability"] is None
        assert result["valid_configurations"] == 0

    def test_baseline_without_a_decision_refuses_to_report_stability(self):
        # Stability relative to a non-decision is undefined; a number here would
        # be an artifact of the baseline choice, not a measurement.
        ambiguous = {
            "configuration_id": "ambiguous",
            "factors": {"backend": "transformers"},
            "points": [
                {"label": "model_a", "quality": 0.80, "cost": 0.005},
                {"label": "model_b", "quality": 0.85, "cost": 0.010},
            ],
        }
        result = decision_stability([ambiguous, SAME], POLICY)
        assert result["status"] == "insufficient_design"
        assert result["stability"] is None
        assert result["baseline_decision"] is None
        assert "undefined" in result["reason"]

    def test_baseline_can_be_selected_explicitly(self):
        result = decision_stability([REVERSED, BASELINE], POLICY, baseline_config="baseline")
        assert result["baseline_config"] == "baseline"
        assert result["baseline_decision"] == "model_a"
        assert result["stability"] == 0.0

    def test_unknown_baseline_configuration_is_rejected(self):
        with pytest.raises(DecisionPolicyError, match="not among the evaluated"):
            decision_stability([BASELINE, SAME], POLICY, baseline_config="nope")

    def test_duplicate_configuration_ids_are_rejected(self):
        with pytest.raises(DecisionPolicyError, match="unique"):
            decision_stability([BASELINE, dict(BASELINE)], POLICY)

    def test_baseline_configuration_is_never_counted_against_itself(self):
        duplicate = dict(BASELINE) | {"configuration_id": "baseline_copy"}
        result = decision_stability([BASELINE, duplicate], POLICY)
        assert result["valid_configurations"] == 1
        assert result["same_decision"] == 1


class TestArtifactIntegrity:
    def test_artifact_carries_evidence_and_disclaimer(self):
        result = decision_stability([BASELINE, SAME], POLICY)
        assert result["disclaimer"] == DECISION_STABILITY_DISCLAIMER
        assert "not production approval" in result["disclaimer"]
        assert result["evidence"]["mode"] == "UNKNOWN"
        assert result["evidence"]["schema_version"] == "1.0"

    def test_evidence_mode_is_preserved_not_upgraded(self):
        result = decision_stability([BASELINE, SAME], POLICY, evidence={"mode": "MOCK"})
        assert result["evidence"]["mode"] == "MOCK"
        assert result["evidence"]["real_model_execution"] is False
        assert "Synthetic evidence is not real model evidence." in result["evidence"][
            "known_limitations"
        ]

    def test_invalid_evidence_claim_is_refused(self):
        # Claiming real execution under a MOCK mode must fail loudly rather than
        # silently upgrade the tier.
        with pytest.raises(ValueError):
            decision_stability(
                [BASELINE, SAME],
                POLICY,
                evidence={"mode": "MOCK", "real_model_execution": True},
            )

    def test_artifact_is_json_serialisable_and_deterministic(self):
        first = decision_stability([BASELINE, SAME, REVERSED], POLICY)
        second = decision_stability([BASELINE, SAME, REVERSED], POLICY)
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
        assert json.loads(json.dumps(first)) == first

    def test_policy_is_echoed_into_the_artifact(self):
        result = decision_stability([BASELINE, SAME], POLICY)
        assert result["policy"] == POLICY.to_dict()
        assert result["policy_name"] == "quality_gate"

    def test_denominator_rule_is_stated_in_the_artifact(self):
        result = decision_stability([BASELINE, SAME], POLICY)
        assert "valid_configurations" in result["denominator_rule"]

    def test_interpretation_never_overstates(self):
        result = decision_stability([BASELINE, REVERSED], POLICY)
        assert "Across 1 valid configuration" in result["interpretation"]
        assert "production" not in result["interpretation"]

    def test_outcome_classifier_is_reachable_for_reuse(self):
        # The classification rules are the part most likely to drift between
        # callers, so they are pinned directly as well as through the artifact.
        assert _classify({"decision": "x", "resolution": "unique_eligible"}, "x") == (
            OUTCOME_SAME,
            "selected the baseline decision",
        )
        assert _classify({"decision": "y", "resolution": "unique_eligible"}, "x")[0] == (
            OUTCOME_REVERSAL
        )
        assert _classify(
            {"decision": None, "resolution": "tie", "tied": ["x", "y"]}, "x"
        )[0] == OUTCOME_TIE_WITH_BASELINE
        assert _classify({"decision": None, "resolution": "tie", "tied": ["y"]}, "x")[0] == (
            OUTCOME_REVERSAL
        )
        assert _classify({"decision": None, "resolution": "no_eligible"}, "x")[0] == (
            OUTCOME_NO_DECISION
        )
        assert _classify({"decision": None, "resolution": "insufficient_evidence"}, "x")[0] == (
            OUTCOME_INVALID
        )

