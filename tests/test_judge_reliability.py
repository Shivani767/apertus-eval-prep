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

