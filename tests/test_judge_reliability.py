"""An LLM judge is an instrument, not ground truth.

The assertions here are mostly about refusals. A judge module is dangerous in
exactly the ways that are easy to implement and hard to notice: inventing an
agreement figure when no reference exists, reporting position bias from
single-order data, and letting an automated record claim human validation. Each
of those is pinned here.
"""

from __future__ import annotations

import json

import pytest

from apertus_eval_prep.judge import (
    JUDGE_DISCLAIMER,
    JudgeRecordError,
    judge_reliability_analysis,
    validate_judge_records,
)
from apertus_eval_prep.deployment_decision import (
    DECISION_OBJECTIVES,
    DeploymentPolicyError,
    analyse_deployment_decision,
)
from apertus_eval_prep.heldout import (
    leave_one_model_out_experiment,
    partition_matrix,
    split_config_keys,
)
from apertus_eval_prep.metamorphic import EXPECTED_RELATION_BY_FAMILY, relation_report
from apertus_eval_prep.multilingual import (
    EXPECTED_RELATION_BY_CONDITION,
    LANGUAGE_CONDITIONS,
    language_sensitivity_report,
)


def _rec(item, candidate="a", verdict="correct", *, position=None,
         rubric="r1", model="gpt-judge-1"):
    record = {
        "item_id": f"i{item}", "candidate_id": candidate, "judge_model": model,
        "judge_revision": "abc123", "judge_prompt": "judge_v1",
        "judge_temperature": 0.0, "rubric_id": rubric, "verdict": verdict,
    }
    if position is not None:
        record["position"] = position
    return record


class TestJudgeProvenance:
    def test_missing_provenance_is_refused(self):
        with pytest.raises(JudgeRecordError, match="missing required provenance"):
            validate_judge_records([{"item_id": "i1", "verdict": "correct"}])

    def test_judge_cannot_claim_human_validation(self):
        # The central safety property: human validation is established by review
        # ingestion, never by an automated judge record.
        with pytest.raises(JudgeRecordError, match="cannot be declared HUMAN_VALIDATED"):
            validate_judge_records([_rec(1) | {"evidence_mode": "HUMAN_VALIDATED"}])

    def test_unknown_verdict_is_refused(self):
        with pytest.raises(JudgeRecordError, match="expected one of"):
            validate_judge_records([_rec(1, verdict="excellent")])

    def test_unknown_position_is_refused(self):
        with pytest.raises(JudgeRecordError, match="position"):
            validate_judge_records([_rec(1, position="first")])

    def test_provenance_is_reported_in_the_artifact(self):
        result = judge_reliability_analysis([_rec(1, rubric="strict", model="judge-x")])
        assert result["judges"] == ["judge-x"]
        assert result["judge_revisions"] == ["abc123"]
        assert result["rubrics"] == ["strict"]
        assert result["judge_prompts"] == ["judge_v1"]
        assert result["temperatures"] == [0.0]


class TestJudgeIsNotTruth:
    def test_judge_is_never_marked_ground_truth(self):
        result = judge_reliability_analysis([_rec(1)])
        assert result["is_ground_truth"] is False
        assert "not ground truth" in result["ground_truth_note"]
        assert "not ground truth" in result["disclaimer"]

    def test_no_reference_means_no_agreement_number(self):
        # A judge agreeing with itself is not a measurement.
        reference = judge_reliability_analysis([_rec(1), _rec(2)])["reference_agreement"]
        assert reference["status"] == "INSUFFICIENT_DATA"
        assert reference["agreement"] is None

    def test_evidence_is_not_upgraded_to_human_validated(self):
        result = judge_reliability_analysis([_rec(1)], evidence={"mode": "SYNTHETIC"})
        assert result["evidence"]["mode"] == "SYNTHETIC"
        assert result["evidence"]["human_reviewed"] is False

    def test_reference_agreement_is_described_as_agreement_only(self):
        result = judge_reliability_analysis(
            [_rec(1, verdict="correct"), _rec(2, verdict="incorrect")],
            reference_verdicts={"i1": "correct", "i2": "correct"},
        )
        reference = result["reference_agreement"]
        assert reference["status"] == "MEASURED"
        assert reference["agreement"] == 0.5
        assert len(reference["disagreements"]) == 1
        assert "not proof of correctness" in reference["note"]


class TestPositionBias:
    def test_swap_test_detects_a_position_preference(self):
        records = [
            _rec(1, verdict="correct", position="A"),
            _rec(1, verdict="incorrect", position="B"),
            _rec(2, verdict="correct", position="A"),
            _rec(2, verdict="incorrect", position="B"),
        ]
        bias = judge_reliability_analysis(records)["position_bias"]
        assert bias["status"] == "MEASURED"
        assert bias["n_swap_pairs"] == 2
        assert bias["mean_position_effect"] == 1.0
        assert bias["position_flipped"] == 2

    def test_position_invariant_judge_reports_no_effect(self):
        records = [_rec(1, verdict="correct", position="A"),
                   _rec(1, verdict="correct", position="B")]
        bias = judge_reliability_analysis(records)["position_bias"]
        assert bias["mean_position_effect"] == 0.0
        assert bias["position_flipped"] == 0

    def test_single_order_data_cannot_reveal_position_bias(self):
        # Reporting a number here would be inventing evidence.
        bias = judge_reliability_analysis([_rec(1, position="A")])["position_bias"]
        assert bias["status"] == "INSUFFICIENT_DATA"
        assert bias["mean_position_effect"] is None
        assert "cannot reveal it" in bias["note"]


class TestSelfConsistencyAndRubric:
    def test_repeated_judging_exposes_the_noise_floor(self):
        records = [_rec(1, verdict="correct"), _rec(1, verdict="incorrect"),
                   _rec(2, verdict="correct"), _rec(2, verdict="correct")]
        consistency = judge_reliability_analysis(records)["self_consistency"]
        assert consistency["status"] == "MEASURED"
        assert consistency["n_repeated_groups"] == 2
        assert consistency["unstable_groups"] == 1

    def test_no_repeats_reports_insufficient_data_not_zero(self):
        consistency = judge_reliability_analysis([_rec(1), _rec(2)])["self_consistency"]
        assert consistency["status"] == "INSUFFICIENT_DATA"
        assert consistency["mean_range"] is None

    def test_rubric_change_can_flip_a_verdict(self):
        records = [_rec(1, verdict="correct", rubric="strict"),
                   _rec(1, verdict="incorrect", rubric="lenient")]
        sensitivity = judge_reliability_analysis(records)["rubric_sensitivity"]
        assert sensitivity["status"] == "MEASURED"
        assert sensitivity["rubric_disagreement"] == 1.0

    def test_single_rubric_reports_insufficient_data(self):
        sensitivity = judge_reliability_analysis([_rec(1)])["rubric_sensitivity"]
        assert sensitivity["status"] == "INSUFFICIENT_DATA"
        assert sensitivity["rubric_disagreement"] is None


class TestArtifact:
    def test_verdict_distribution_is_reported(self):
        result = judge_reliability_analysis(
            [_rec(1, verdict="correct"), _rec(2, verdict="incorrect"),
             _rec(3, verdict="incorrect")]
        )
        assert result["verdict_distribution"] == {"correct": 1, "incorrect": 2}

    def test_disclaimer_denies_production_approval(self):
        result = judge_reliability_analysis([_rec(1)])
        assert result["disclaimer"] == JUDGE_DISCLAIMER
        assert "not ground truth" in result["disclaimer"]

    def test_deterministic_and_json_safe(self):
        records = [_rec(1, position="A"), _rec(1, position="B", verdict="incorrect")]
        first = judge_reliability_analysis(records)
        second = judge_reliability_analysis(records)
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
        assert json.loads(json.dumps(first)) == first


class TestMetamorphicRelations:
    def _pair(self, pid, *, original, transformed, family="paraphrase",
              model="m1", language="en"):
        return {
            "perturbation_id": pid, "source_item_id": f"s{pid}", "family": family,
            "model": model, "language": language,
            "original_correct": original, "transformed_correct": transformed,
        }

    def test_held_and_violated_relations_are_separated(self):
        report = relation_report([
            self._pair("p1", original=True, transformed=True),
            self._pair("p2", original=True, transformed=False),
        ])
        assert report["failure_categories"]["relation_held"] == 1
        assert report["failure_categories"]["relation_violated"] == 1
        assert report["metamorphic_consistency"] == 0.5

    def test_missing_observation_is_never_a_violation(self):
        # An unmeasured input cannot violate a relation; counting it as one
        # would turn missing data into a model failure.
        report = relation_report([
            self._pair("p1", original=True, transformed=True),
            self._pair("p2", original=True, transformed=None),
        ])
        assert report["failure_categories"]["insufficient_observation"] == 1
        assert report["failure_categories"]["relation_violated"] == 0
        assert report["n_measured"] == 1
        assert report["metamorphic_consistency"] == 1.0

    def test_expected_relation_is_declared_not_inferred(self):
        assert all(rel == "invariant" for rel in EXPECTED_RELATION_BY_FAMILY.values())
        report = relation_report([self._pair("p1", original=True, transformed=True)])
        assert report["pairs"][0]["expected_relation"] == "invariant"
        assert report["expected_relations"]["paraphrase"] == "invariant"

    def test_explicit_expected_relation_is_respected(self):
        pair = self._pair("p1", original=True, transformed=False) | {
            "expected_relation": "variant"}
        report = relation_report([pair])
        assert report["pairs"][0]["relation_holds"] is True
        assert report["failure_categories"]["relation_held"] == 1

    def test_model_and_language_breakdowns_are_separate(self):
        report = relation_report([
            self._pair("p1", original=True, transformed=True, model="m1", language="en"),
            self._pair("p2", original=True, transformed=False, model="m1", language="en"),
            self._pair("p3", original=True, transformed=False, model="m2", language="hi"),
        ])
        assert report["by_model"]["m1"]["consistency"] == 0.5
        assert report["by_model"]["m2"]["consistency"] == 0.0
        assert report["by_language"]["en"]["consistency"] == 0.5
        assert report["by_language"]["hi"]["consistency"] == 0.0

    def test_no_measured_pairs_reports_insufficient_design(self):
        report = relation_report([self._pair("p1", original=None, transformed=None)])
        assert report["status"] == "insufficient_design"
        assert report["metamorphic_consistency"] is None

    def test_semantic_equivalence_is_not_claimed(self):
        report = relation_report([self._pair("p1", original=True, transformed=True)])
        assert any("not evidence of semantic equivalence" in lim for lim in report["limits"])
        assert "semantically equivalent" in report["disclaimer"]
        assert "NOT evidence" in report["disclaimer"]

    def test_report_is_deterministic_and_json_safe(self):
        pairs = [self._pair("p1", original=True, transformed=False)]
        first, second = relation_report(pairs), relation_report(pairs)
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
        assert json.loads(json.dumps(first)) == first


class TestHeldoutLeakage:
    """Tests written to CATCH leakage, not to record that a guard exists.

    A held-out estimate means nothing if the held-out cells informed the fit.
    These try to make leakage happen -- duplicate config keys, an oversized
    budget, a mismatched matrix -- and assert the platform refuses rather than
    returning a flattering number.
    """

    CONFIGS = [f"cfg_{i}" for i in range(6)]

    def _matrix(self, n_models=3):
        # Distinct per-column values, so any leak would be visible in the cells.
        return [[0.1 * (c + 1) + 0.01 * m for c in range(len(self.CONFIGS))]
                for m in range(n_models)]

    def test_train_and_heldout_are_disjoint(self):
        split = split_config_keys(self.CONFIGS, budget=3, seed=0)
        assert not set(split["train"]) & set(split["heldout"])
        assert len(split["train"]) + len(split["heldout"]) == len(self.CONFIGS)

    def test_duplicate_config_keys_collapse_and_stay_accounted_for(self):
        # Passing a key twice must not create a phantom training cell.
        split = split_config_keys(self.CONFIGS + self.CONFIGS, budget=3, seed=0)
        assert split["n_total"] == len(set(self.CONFIGS))
        assert not set(split["train"]) & set(split["heldout"])

    def test_budget_larger_than_the_space_is_refused(self):
        # Training on everything leaves nothing held out; the platform must say
        # so rather than report an in-sample fit as generalisation.
        with pytest.raises(ValueError, match="exceeds the configuration space"):
            split_config_keys(self.CONFIGS, budget=len(self.CONFIGS) + 1)

    def test_budget_below_one_is_refused(self):
        with pytest.raises(ValueError, match="budget must be >= 1"):
            split_config_keys(self.CONFIGS, budget=0)

    def test_mismatched_matrix_width_is_refused(self):
        split = split_config_keys(self.CONFIGS, budget=3, seed=0)
        with pytest.raises(ValueError, match="config columns but split expects"):
            partition_matrix([[0.1, 0.2]], split)

    def test_partition_keeps_train_and_heldout_disjoint(self):
        split = split_config_keys(self.CONFIGS, budget=3, seed=0)
        train, heldout = partition_matrix(self._matrix(), split)
        assert len(train[0]) == 3 and len(heldout[0]) == 3
        for row_train, row_hold in zip(train, heldout):
            assert not set(row_train) & set(row_hold)

    def test_split_is_deterministic_for_a_given_seed(self):
        assert (split_config_keys(self.CONFIGS, budget=3, seed=7)
                == split_config_keys(self.CONFIGS, budget=3, seed=7))

    def test_different_seeds_give_different_partitions(self):
        a = split_config_keys(self.CONFIGS, budget=3, seed=1)
        b = split_config_keys(self.CONFIGS, budget=3, seed=2)
        assert (a["train"], a["heldout"]) != (b["train"], b["heldout"])

    def test_leave_one_model_out_never_trains_on_the_hidden_model(self):
        report = leave_one_model_out_experiment(
            self._matrix(n_models=4), self.CONFIGS, budget=3, seed=0)
        hidden = report["hidden_model_index"]
        assert hidden is not None
        # One model is hidden, so the visible count is one fewer than the total.
        assert report["n_visible_models"] == 4 - 1
        assert hidden not in range(report["n_visible_models"]) or hidden == 3
        assert "hidden model excluded from all fitting" in report["provenance"]

    def test_leave_one_model_out_reports_its_own_low_power(self):
        # With four models this is a probe, not evidence of generalization, and
        # the artifact must say so rather than invite the stronger reading.
        report = leave_one_model_out_experiment(
            self._matrix(n_models=4), self.CONFIGS, budget=3, seed=0)
        assert "low-power" in report["power_note"]


class TestMultilingualTrack:
    """Code-switching is expected to move the score; that is the finding.

    The dangerous mistake here is treating a language effect as a metamorphic
    violation. ``hinglish`` declares ``not_invariant`` precisely so a real
    performance change is reported as a measurement, and the tracker must never
    quietly promote it to a failure.
    """

    def _rows(self, n=4, include_unknown=False):
        rows = []
        for index in range(n):
            rows.append({"item_id": f"i{index}", "condition": "en",
                         "score": 0.8, "model": "m1"})
            rows.append({"item_id": f"i{index}", "condition": "hi",
                         "score": 0.6, "model": "m1"})
            rows.append({"item_id": f"i{index}", "condition": "hinglish",
                         "score": 0.5, "model": "m1"})
        if include_unknown:
            rows.append({"item_id": "iX", "condition": "klingon", "score": 0.9})
        return rows

    def test_declared_conditions_are_exactly_three(self):
        assert LANGUAGE_CONDITIONS == ("en", "hi", "hinglish")
        assert set(EXPECTED_RELATION_BY_CONDITION) == set(LANGUAGE_CONDITIONS)

    def test_code_switched_condition_is_not_declared_invariant(self):
        # This is the whole point: a real code-switching effect is expected.
        assert EXPECTED_RELATION_BY_CONDITION["hinglish"] == "not_invariant"
        assert EXPECTED_RELATION_BY_CONDITION["en"] == "invariant"

    def test_paired_deltas_are_measured_against_the_reference(self):
        report = language_sensitivity_report(self._rows())
        by_condition = {c["condition"]: c for c in report["comparison"]}
        assert by_condition["hi"]["mean_delta_vs_reference"] == pytest.approx(-0.2)
        assert by_condition["hinglish"]["mean_delta_vs_reference"] == pytest.approx(-0.3)
        assert by_condition["hi"]["n_paired_items"] == 4
        assert report["status"] == "ok"

    def test_only_items_shared_with_the_reference_are_paired(self):
        rows = self._rows(n=2) + [
            {"item_id": "extra", "condition": "hi", "score": 0.1, "model": "m1"},
        ]
        report = language_sensitivity_report(rows)
        by_condition = {c["condition"]: c for c in report["comparison"]}
        # The unpaired item is excluded rather than diluting the comparison.
        assert by_condition["hi"]["n_paired_items"] == 2

    def test_unpaired_condition_is_unavailable_not_zero(self):
        rows = [{"item_id": "i0", "condition": "en", "score": 0.8},
                {"item_id": "other", "condition": "hi", "score": 0.1}]
        report = language_sensitivity_report(rows)
        by_condition = {c["condition"]: c for c in report["comparison"]}
        assert by_condition["hi"]["status"] == "UNAVAILABLE"
        assert by_condition["hi"]["mean_delta_vs_reference"] is None
        assert "not a zero delta" in by_condition["hi"]["reason"]

    def test_missing_conditions_are_named(self):
        rows = [{"item_id": "i0", "condition": "en", "score": 0.8},
                {"item_id": "i0", "condition": "hi", "score": 0.7}]
        report = language_sensitivity_report(rows)
        assert report["conditions_missing"] == ["hinglish"]

    def test_unknown_conditions_are_ignored_and_listed(self):
        report = language_sensitivity_report(self._rows(include_unknown=True))
        assert report["unknown_conditions_ignored"] == ["klingon"]
        assert "klingon" not in report["conditions_observed"]

    def test_undeclared_reference_is_rejected(self):
        with pytest.raises(ValueError, match="not a declared condition"):
            language_sensitivity_report(self._rows(), reference_condition="fr")

    def test_no_language_ranking_is_asserted(self):
        report = language_sensitivity_report(self._rows())
        assert "not a language ranking" in " ".join(report["limits"])
        assert "no language ranking is asserted" in report["disclaimer"]

    def test_evidence_and_determinism(self):
        first = language_sensitivity_report(self._rows(), evidence={"mode": "MOCK"})
        second = language_sensitivity_report(self._rows(), evidence={"mode": "MOCK"})
        assert first["evidence"]["mode"] == "MOCK"
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


class TestDeploymentDecision:
    """Memory is a capacity ceiling, and an unmeasured one is not 0 GB.

    The tempting failure is to treat a missing memory reading as zero, which
    makes an unmeasured option pass every memory budget and look optimal. Here
    the best-quality, lowest-latency option has NO memory figure; it must be
    excluded, not selected, and the decision labelled partial.
    """

    POINTS = [
        {"label": "accurate_but_40gb", "quality": 0.90,
         "latency_p95_ms": 800, "cost": 0.02, "memory_gb": 40},
        {"label": "lean", "quality": 0.75,
         "latency_p95_ms": 300, "cost": 0.01, "memory_gb": 8},
        {"label": "best_but_unmeasured", "quality": 0.95,
         "latency_p95_ms": 250, "cost": 0.01},
    ]
    CONSTRAINTS = {"quality": 0.70, "max_latency_p95_ms": 1000, "max_memory_gb": 24}

    def test_four_objectives_including_memory(self):
        assert DECISION_OBJECTIVES["memory_gb"] == "min"
        assert set(DECISION_OBJECTIVES) == {
            "quality", "latency_p95_ms", "cost", "memory_gb"}

    def test_unmeasured_memory_is_excluded_not_treated_as_zero(self):
        result = analyse_deployment_decision(self.POINTS, constraints=self.CONSTRAINTS)
        excluded = [e["label"] for e in result["excluded_for_unmeasured_objectives"]]
        assert excluded == ["best_but_unmeasured"]
        # The option with the best quality and lowest latency is NOT selected.
        assert result["decision"] != "best_but_unmeasured"
        assert result["decision"] == "lean"

    def test_decision_is_labelled_partial_when_a_decisive_objective_is_unmeasured(self):
        result = analyse_deployment_decision(self.POINTS, constraints=self.CONSTRAINTS)
        assert result["decision_completeness"] == "partial"
        assert result["unmeasured_decisive_objectives"] == ["memory_gb"]

    def test_complete_decision_when_everything_is_measured(self):
        result = analyse_deployment_decision(self.POINTS[:2], constraints=self.CONSTRAINTS)
        assert result["decision_completeness"] == "complete"
        assert result["n_incomplete"] == 0

    def test_memory_budget_rejects_an_option_that_exceeds_it(self):
        result = analyse_deployment_decision(self.POINTS, constraints=self.CONSTRAINTS)
        rejected = {r["label"]: r["reasons"] for r in result["rejections"]}
        assert "memory_gb" in rejected["accurate_but_40gb"][0]
        assert "maximum 24" in rejected["accurate_but_40gb"][0]

    def test_objective_coverage_is_reported_per_objective(self):
        result = analyse_deployment_decision(self.POINTS)
        assert result["objective_coverage"]["memory_gb"]["unmeasured"] == 1
        assert result["objective_coverage"]["quality"]["unmeasured"] == 0

    def test_aliases_are_honoured(self):
        points = [{"label": "aliased", "quality": 0.8, "p95_ms": 300,
                   "cost_value": 0.01, "peak_memory_gb": 8}]
        result = analyse_deployment_decision(points)
        assert result["n_complete"] == 1

    def test_no_constraints_reports_no_selection(self):
        result = analyse_deployment_decision(self.POINTS)
        assert result["selection_status"] == "NO_CONSTRAINTS"
        assert result["decision"] is None

    def test_invalid_objective_direction_is_rejected(self):
        with pytest.raises(DeploymentPolicyError, match="expected min or max"):
            analyse_deployment_decision(self.POINTS, objectives={"quality": "higher"})

    def test_disclaimer_denies_approval_and_capacity_guarantee(self):
        result = analyse_deployment_decision(self.POINTS)
        assert "not a production approval" in result["disclaimer"]
        assert "capacity guarantee" in result["disclaimer"]

    def test_report_is_deterministic_and_json_safe(self):
        first = analyse_deployment_decision(self.POINTS, constraints=self.CONSTRAINTS)
        second = analyse_deployment_decision(self.POINTS, constraints=self.CONSTRAINTS)
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)

