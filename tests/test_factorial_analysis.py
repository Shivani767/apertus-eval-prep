"""Interaction analysis must refuse an OFAT design, not analyse it.

The failure guarded against is subtle and common: running a main-effects
analysis on one-factor-at-a-time data and reporting "no interaction detected".
That is not a null result. In an OFAT design the cell where both factors differ
was never run, so the interaction is unmeasured. The artifact has to say so in a
field a reader actually sees, which is why `design_kind` and
`unavailable_pairs` are top-level rather than buried in per-pair diagnostics.
"""

from __future__ import annotations

import json

import pytest

from apertus_eval_prep.factorial import (
    FACTORIAL,
    OFAT,
    PARTIALLY_CROSSED,
    analyse_interactions,
    classify_design,
)

CROSSOVER = {("a1", "b1"): 0.50, ("a1", "b2"): 0.80,
             ("a2", "b1"): 0.80, ("a2", "b2"): 0.50}
ADDITIVE = {("a1", "b1"): 0.50, ("a1", "b2"): 0.60,
            ("a2", "b1"): 0.60, ("a2", "b2"): 0.70}


def _design(cell_means, reps=3, noise=(0.0, 0.01, -0.01)):
    rows = []
    for a in ("a1", "a2"):
        for b in ("b1", "b2"):
            for offset in noise[:reps]:
                rows.append({"a": a, "b": b, "score": cell_means[(a, b)] + offset})
    return rows


OFAT_ROWS = [
    {"prompt": "baseline", "backend": "hf", "score": 0.50},
    {"prompt": "fewshot", "backend": "hf", "score": 0.60},
    {"prompt": "baseline", "backend": "vllm", "score": 0.70},
]


def _three_factor_rows():
    """One factor vocabulary where (a, b) is crossed and (a, c) is not.

    ``c`` has a single level, so the (a, c) interaction was never run while
    (a, b) was -- a partially crossed design from one consistent vocabulary.
    """
    rows = []
    for a in ("a1", "a2"):
        for b in ("b1", "b2"):
            for offset in (0.0, 0.01, -0.01):
                rows.append({"a": a, "b": b, "c": "c1", "score": 0.5 + 0.05 * offset + 0.02 * len(b)})
    return rows


class TestDesignClassification:
    def test_ofat_is_recognised(self):
        assert classify_design(OFAT_ROWS, [("prompt", "backend")]) == OFAT

    def test_crossed_design_is_factorial(self):
        assert classify_design(_design(CROSSOVER), [("a", "b")]) == FACTORIAL

    def test_mixed_pairs_are_partially_crossed(self):
        rows = _three_factor_rows()
        assert classify_design(rows, [("a", "b"), ("a", "c")]) == PARTIALLY_CROSSED

    def test_rows_missing_a_factor_do_not_create_phantom_cells(self):
        # A row that never mentions a factor must not become a "None" level:
        # that would invent a cell the design never ran.
        rows = _design(CROSSOVER) + OFAT_ROWS
        result = analyse_interactions(rows, [("a", "b")])
        report = result["pairs"][0]
        assert report["n_rows_without_both_factors"] == len(OFAT_ROWS)
        assert report["n_rows_considered"] == len(_design(CROSSOVER))
        assert "None" not in report["diagnostics"]["a_levels"]



class TestOfatRefusal:
    def test_ofat_data_yields_no_estimate(self):
        result = analyse_interactions(OFAT_ROWS, [("prompt", "backend")])
        assert result["status"] == "insufficient_design"
        assert result["design_kind"] == OFAT
        assert result["n_pairs_measured"] == 0
        assert result["n_effects_tested"] == 0
        assert result["unavailable_pairs"] == [["prompt", "backend"]]

    def test_ofat_never_reports_an_interaction_p_value(self):
        # The central assertion: absence of measurement is not absence of effect.
        result = analyse_interactions(OFAT_ROWS, [("prompt", "backend")])
        for report in result["pairs"]:
            for effect in report["effects"].values():
                assert effect["p_value"] is None
                assert effect["omega2_pct"] is None
                assert effect["status"] == "UNAVAILABLE"

    def test_design_note_explains_why(self):
        note = analyse_interactions(OFAT_ROWS, [("prompt", "backend")])["design_note"]
        assert "OFAT" in note
        assert "structurally" in note

    def test_limits_state_unavailable_is_not_null(self):
        limits = analyse_interactions(OFAT_ROWS, [("prompt", "backend")])["limits"]
        assert any("not a null result" in limit for limit in limits)

    def test_interpretation_does_not_claim_a_null_finding(self):
        text = analyse_interactions(OFAT_ROWS, [("prompt", "backend")])["interpretation"]
        assert "no requested pair could be decomposed" in text
        assert "no interaction" not in text.lower()


class TestMeasuredInteraction:
    def test_crossover_interaction_is_reported_with_size_and_uncertainty(self):
        result = analyse_interactions(_design(CROSSOVER), [("a", "b")], n_boot=200)
        assert result["status"] == "ok"
        assert result["design_kind"] == FACTORIAL
        effect = result["pairs"][0]["effects"]["interaction"]
        assert effect["omega2_pct"] > 50.0
        assert effect["kind"] == "interaction"
        assert effect["p_value"] is not None
        lo, hi = effect["bootstrap_ci95_pct"]
        assert lo <= effect["omega2_pct"] / 100 <= hi

    def test_main_effects_are_labelled_with_their_factor(self):
        effects = analyse_interactions(_design(ADDITIVE), [("a", "b")])["pairs"][0]["effects"]
        assert effects["factor_a"]["factor"] == "a"
        assert effects["factor_b"]["factor"] == "b"
        assert effects["factor_a"]["kind"] == "main_effect"
        assert effects["interaction"]["kind"] == "interaction"

    def test_significance_is_separated_from_magnitude(self):
        result = analyse_interactions(_design(CROSSOVER), [("a", "b")])
        assert any("practical importance" in limit for limit in result["limits"])
        assert result["disclaimer"]

    def test_correction_is_recorded_with_the_number_of_tests(self):
        result = analyse_interactions(_design(ADDITIVE), [("a", "b")])
        assert result["multiple_comparison_correction"] == "holm_bonferroni"
        assert result["n_effects_tested"] >= 1

    def test_benjamini_hochberg_correction_is_available(self):
        result = analyse_interactions(
            _design(ADDITIVE), [("a", "b")], correction="benjamini_hochberg"
        )
        assert result["multiple_comparison_correction"] == "benjamini_hochberg"

    def test_uncorrected_is_allowed_but_declared(self):
        result = analyse_interactions(_design(ADDITIVE), [("a", "b")], correction="none")
        assert result["multiple_comparison_correction"] == "none"

    def test_unknown_correction_is_rejected(self):
        with pytest.raises(ValueError, match="unsupported correction"):
            analyse_interactions(_design(ADDITIVE), [("a", "b")], correction="bogus")

    def test_corrected_p_is_never_smaller_than_raw_p(self):
        result = analyse_interactions(_design(ADDITIVE), [("a", "b")])
        for report in result["pairs"]:
            for effect in report["effects"].values():
                if effect["p_value"] is not None and effect["p_value_corrected"] is not None:
                    assert effect["p_value_corrected"] >= effect["p_value"] - 1e-9

    def test_partial_pair_listing_keeps_both_kinds_visible(self):
        rows = _three_factor_rows()
        result = analyse_interactions(rows, [("a", "b"), ("a", "c")])
        assert result["n_pairs_measured"] == 1
        assert result["n_pairs_requested"] == 2
        assert result["unavailable_pairs"] == [["a", "c"]]
        assert result["design_kind"] == PARTIALLY_CROSSED


class TestArtifactIntegrity:
    def test_artifact_is_json_safe_and_deterministic(self):
        first = analyse_interactions(_design(CROSSOVER), [("a", "b")], n_boot=50, seed=3)
        second = analyse_interactions(_design(CROSSOVER), [("a", "b")], n_boot=50, seed=3)
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
        assert json.loads(json.dumps(first)) == first

    def test_internal_helpers_are_not_leaked(self):
        blob = json.dumps(analyse_interactions(_design(ADDITIVE), [("a", "b")]))
        assert "_raw_p" not in blob
        assert "_corrected_p" not in blob

    def test_evidence_mode_is_preserved(self):
        result = analyse_interactions(_design(ADDITIVE), [("a", "b")], evidence={"mode": "MOCK"})
        assert result["evidence"]["mode"] == "MOCK"
        assert result["evidence"]["real_model_execution"] is False

    def test_disallowed_evidence_upgrade_is_refused(self):
        with pytest.raises(ValueError):
            analyse_interactions(
                _design(ADDITIVE), [("a", "b")],
                evidence={"mode": "MOCK", "real_model_execution": True},
            )

    def test_no_pairs_requested_is_handled(self):
        result = analyse_interactions(_design(ADDITIVE), [])
        assert result["status"] == "insufficient_design"
        assert "No factor pairs" in result["interpretation"]

