"""Ranking stability must expose disagreement between metrics, not average it away.

A single composite "stability score" is the tempting design and the wrong one:
top-1 stability, top-k set stability, Kendall tau and pairwise inversion can
and do disagree, and which one matters depends on how many models a deployment
actually ships. These tests pin the individual definitions and, just as
importantly, pin a case where the metrics genuinely conflict.
"""

from __future__ import annotations

import json

import pytest

from apertus_eval_prep.ranking import (
    RANKING_STABILITY_DISCLAIMER,
    rank_reversal_rate,
    ranking_stability_report,
    top_k_set_stability,
)

MODELS = ["m_a", "m_b", "m_c"]
BASELINE = [0.72, 0.65, 0.51]


class TestRankReversalRate:
    def test_identical_ordering_is_not_a_reversal(self):
        result = rank_reversal_rate(MODELS, BASELINE, [[0.70, 0.66, 0.52]])
        assert result["rank_reversal_rate"] == 0.0
        assert result["changed_orderings"] == 0
        assert result["valid_perturbations"] == 1

    def test_leader_change_counts_as_a_reversal(self):
        result = rank_reversal_rate(MODELS, BASELINE, [[0.61, 0.74, 0.55]])
        assert result["rank_reversal_rate"] == 1.0
        assert result["changed"][0]["order"][0] == "m_b"

    def test_deep_pair_flip_counts_as_a_reversal_too(self):
        result = rank_reversal_rate(MODELS, BASELINE, [[0.70, 0.55, 0.66]])
        assert result["rank_reversal_rate"] == 1.0
        assert result["changed"][0]["pairwise_inversions"] == 1

    def test_unmeasured_model_is_incomparable_not_stable(self):
        result = rank_reversal_rate(MODELS, BASELINE, [[0.70, 0.66, None]])
        assert result["valid_perturbations"] == 0
        assert result["rank_reversal_rate"] is None
        assert len(result["incomparable"]) == 1
        assert "not measured" in result["incomparable"][0]["reason"]

    def test_incomparable_perturbations_leave_the_denominator(self):
        result = rank_reversal_rate(
            MODELS, BASELINE, [[0.70, 0.66, 0.52], [0.61, 0.74, 0.55], [0.70, 0.66, None]]
        )
        assert result["valid_perturbations"] == 2
        assert result["rank_reversal_rate"] == 0.5

    def test_no_perturbations_gives_none_not_zero(self):
        # Zero reversions out of zero measurements is not evidence of stability.
        result = rank_reversal_rate(MODELS, BASELINE, [])
        assert result["rank_reversal_rate"] is None
        assert result["valid_perturbations"] == 0

    def test_ties_are_ordered_deterministically(self):
        first = rank_reversal_rate(MODELS, [0.5, 0.5, 0.1], [[0.5, 0.5, 0.1]])
        second = rank_reversal_rate(MODELS, [0.5, 0.5, 0.1], [[0.5, 0.5, 0.1]])
        assert first["baseline_order"] == second["baseline_order"]
        assert first["rank_reversal_rate"] == 0.0

    def test_definition_is_stated_in_the_artifact(self):
        assert "valid perturbations" in rank_reversal_rate(MODELS, BASELINE, [])["definition"]


class TestTopKStability:
    def test_top_k_set_survives_a_swap_that_changes_the_order(self):
        # The deployed pair {m_a, m_b} is unchanged; only their order moved.
        result = top_k_set_stability(MODELS, BASELINE, [[0.61, 0.74, 0.55]], k=2)
        assert result["top_k_stability"] == 1.0
        assert result["top_k_exact_order_stability"] == 0.0

    def test_top_k_set_changes_when_a_model_is_displaced(self):
        result = top_k_set_stability(MODELS, BASELINE, [[0.40, 0.50, 0.80]], k=2)
        assert result["top_k_stability"] == 0.0

    def test_unmeasured_rows_are_excluded_from_top_k(self):
        result = top_k_set_stability(MODELS, BASELINE, [[0.61, 0.74, 0.55], [0.7, 0.6, None]], k=1)
        assert result["valid_perturbations"] == 1
        assert result["top_k_stability"] == 0.0

    def test_invalid_k_is_rejected(self):
        with pytest.raises(ValueError, match="k must be >= 1"):
            top_k_set_stability(MODELS, BASELINE, [], k=0)

    def test_undefined_baseline_ordering_reports_none(self):
        result = top_k_set_stability(MODELS, [0.7, 0.6, None], [], k=1)
        assert result["top_k_stability"] is None
        assert "undefined" in result["reason"]


class TestReport:
    def test_metrics_are_reported_separately_with_no_composite(self):
        report = ranking_stability_report(
            MODELS, BASELINE, [[0.70, 0.66, 0.52], [0.61, 0.74, 0.55]], k=2
        )
        assert report["composite_score"] is None
        assert "composite" in report["composite_rationale"].lower()
        for key in (
            "rank_reversal_rate",
            "top_1_stability",
            "top_k_stability",
            "mean_kendall_tau",
            "mean_pairwise_inversion_rate",
        ):
            assert key in report

    def test_top_one_and_top_two_can_disagree(self):
        # The case that justifies refusing a composite: the leader changes but
        # the deployed pair does not, so both readings are true at once.
        report = ranking_stability_report(MODELS, BASELINE, [[0.61, 0.74, 0.55]], k=2)
        assert report["top_1_stability"] == 0.0
        assert report["top_k_stability"] == 1.0

    def test_kendall_and_inversion_rate_are_reported(self):
        # Baseline ranks m_a>m_b>m_c; the perturbation swaps only the top pair,
        # so one of three pairs is discordant: tau = (2-1)/3 and one inversion.
        report = ranking_stability_report(MODELS, BASELINE, [[0.61, 0.74, 0.55]])
        assert report["mean_kendall_tau"] == pytest.approx(1 / 3)
        assert report["mean_pairwise_inversion_rate"] == pytest.approx(1 / 3)

    def test_disclaimer_and_evidence_are_attached(self):
        report = ranking_stability_report(
            MODELS, BASELINE, [[0.61, 0.74, 0.55]], evidence={"mode": "MOCK"}
        )
        assert report["disclaimer"] == RANKING_STABILITY_DISCLAIMER
        assert "production approval" in report["disclaimer"]
        assert report["evidence"]["mode"] == "MOCK"

    def test_report_is_json_serialisable_and_deterministic(self):
        first = ranking_stability_report(MODELS, BASELINE, [[0.61, 0.74, 0.55]])
        second = ranking_stability_report(MODELS, BASELINE, [[0.61, 0.74, 0.55]])
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
        assert json.loads(json.dumps(first)) == first

    def test_incomparable_perturbations_are_surfaced(self):
        report = ranking_stability_report(MODELS, BASELINE, [[0.7, 0.6, None]])
        assert report["incomparable_perturbations"] == 1
        assert report["rank_reversal_rate"] is None

