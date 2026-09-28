"""F tests and factorial interaction analysis: correct arithmetic, honest limits.

Two things are defended here. First, the F distribution itself, implemented in
``stats`` rather than imported because scipy is not a project dependency -- so
it is pinned against *published* critical values, never against itself.
Second, the refusal path: an F statistic with no residual degrees of freedom
must be reported as UNAVAILABLE rather than as infinity, and an OFAT design must
not be forced through an ANOVA its design cannot support.
"""

from __future__ import annotations

import pytest

from apertus_eval_prep.stats import betainc_reg, f_sf
from apertus_eval_prep.variance import (
    factorial_diagnostics,
    factorial_variance_decomposition,
    interaction_screen,
)


class TestFDistribution:
    @pytest.mark.parametrize(
        "df1,df2,critical",
        [
            (1, 10, 4.9646),
            (2, 10, 4.1028),
            (3, 10, 3.7083),
            (1, 1, 161.4476),
            (2, 20, 3.4928),
            (1, 30, 4.1712),
            (4, 20, 2.8660),
            (1, 100, 3.9371),
        ],
    )
    def test_published_five_percent_critical_values(self, df1, df2, critical):
        # Published 0.05 critical values: P(F > critical) must be 0.05.
        assert f_sf(critical, df1, df2) == pytest.approx(0.05, abs=5e-5)

    @pytest.mark.parametrize(
        "df1,df2,critical",
        [
            (1, 10, 10.0448),  # t(10)_{.995}^2
            (1, 20, 8.0957),   # t(20)_{.995}^2
            (1, 30, 7.5625),   # t(30)_{.995}^2
            (2, 10, 7.5594),
        ],
    )
    def test_published_one_percent_critical_values(self, df1, df2, critical):
        assert f_sf(critical, df1, df2) == pytest.approx(0.01, abs=5e-5)

    def test_survival_is_monotone_decreasing(self):
        values = [f_sf(f, 2, 10) for f in (0.5, 1.0, 2.0, 5.0, 10.0, 50.0)]
        assert values == sorted(values, reverse=True)
        assert all(0.0 <= v <= 1.0 for v in values)

    def test_non_positive_statistic_is_entirely_in_the_tail(self):
        assert f_sf(0.0, 1, 10) == 1.0
        assert f_sf(-3.0, 1, 10) == 1.0

    def test_invalid_degrees_of_freedom_are_rejected(self):
        with pytest.raises(ValueError):
            f_sf(1.0, 0, 10)
        with pytest.raises(ValueError):
            f_sf(1.0, 1, 0)

    def test_regularized_incomplete_beta_satisfies_its_symmetry(self):
        # I_x(a,b) + I_{1-x}(b,a) == 1
        for a, b, x in [(0.5, 2.0, 0.3), (2.0, 0.5, 0.8), (3.0, 3.0, 0.5)]:
            assert betainc_reg(a, b, x) + betainc_reg(b, a, 1 - x) == pytest.approx(1.0, abs=1e-12)

    def test_regularized_incomplete_beta_endpoints(self):
        assert betainc_reg(2.0, 3.0, 0.0) == 0.0
        assert betainc_reg(2.0, 3.0, 1.0) == 1.0


def _balanced_2x2(cell_means, reps=3, noise=(0.0, 0.01, -0.01)):
    """Build a balanced complete 2x2 design with the given cell means."""
    rows = []
    for a in ("a1", "a2"):
        for b in ("b1", "b2"):
            for offset in noise[:reps]:
                rows.append({"a": a, "b": b, "score": cell_means[(a, b)] + offset})
    return rows


ADDITIVE = {("a1", "b1"): 0.50, ("a1", "b2"): 0.60,
            ("a2", "b1"): 0.60, ("a2", "b2"): 0.70}
CROSSOVER = {("a1", "b1"): 0.50, ("a1", "b2"): 0.80,
             ("a2", "b1"): 0.80, ("a2", "b2"): 0.50}


class TestFactorialFTests:
    def test_main_effects_measured_and_interaction_absent(self):
        rows = _balanced_2x2(ADDITIVE)
        result = factorial_variance_decomposition(rows, "a", "b")
        assert result["status"] == "MEASURED"
        tests = result["f_tests"]
        assert tests["factor_a"]["status"] == "MEASURED"
        assert tests["factor_b"]["status"] == "MEASURED"
        # Symmetric by construction.
        assert tests["factor_a"]["f"] == pytest.approx(tests["factor_b"]["f"])
        assert result["effect_sizes_omega2_pct"]["factor_a"] == pytest.approx(
            result["effect_sizes_omega2_pct"]["factor_b"]
        )
        # No interaction by construction.
        assert tests["interaction"]["p_value"] == pytest.approx(1.0)
        assert result["effect_sizes_omega2_pct"]["interaction"] == pytest.approx(0.0)

    def test_crossover_interaction_is_detected(self):
        # A helps under b1 and hurts under b2, so the main effects cancel and
        # the interaction is the whole story. This is precisely the effect an
        # OFAT design cannot see.
        result = factorial_variance_decomposition(_balanced_2x2(CROSSOVER), "a", "b")
        assert result["effect_sizes_omega2_pct"]["interaction"] > 50.0
        assert result["f_tests"]["interaction"]["p_value"] < 0.01
        assert result["effect_sizes_omega2_pct"]["factor_a"] < 1.0

    def test_variance_fractions_sum_to_one(self):
        result = factorial_variance_decomposition(_balanced_2x2(ADDITIVE), "a", "b")
        assert sum(result["variance_fractions"].values()) == pytest.approx(1.0, abs=1e-4)

    def test_unreplicated_design_has_no_error_degrees_of_freedom(self):
        # One observation per cell: there is no error variance to test against,
        # so F is undefined. Reporting infinity here would be a fabrication.
        rows = _balanced_2x2(ADDITIVE, reps=1, noise=(0.0,))
        result = factorial_variance_decomposition(rows, "a", "b")
        assert result["f_tests"]["df_error"] == 0
        for term in ("factor_a", "factor_b", "interaction"):
            assert result["f_tests"][term]["status"] == "UNAVAILABLE"
            assert result["f_tests"][term]["f"] is None
            assert result["f_tests"][term]["p_value"] is None
            assert "residual degrees of freedom" in result["f_tests"][term]["reason"]
        # The variance partition itself is still supported by the design.
        assert result["status"] == "MEASURED"

    def test_significance_is_not_presented_as_importance(self):
        note = factorial_variance_decomposition(_balanced_2x2(ADDITIVE), "a", "b")["f_tests"]["note"]
        assert "practical importance" in note

    def test_ofat_design_is_refused_not_forced(self):
        # A control plus one level varied at a time is not a crossed design.
        rows = [
            {"a": "a1", "b": "b1", "score": 0.50},
            {"a": "a2", "b": "b1", "score": 0.60},
            {"a": "a1", "b": "b2", "score": 0.70},
        ]
        result = factorial_variance_decomposition(rows, "a", "b")
        assert result["status"] == "UNAVAILABLE"
        assert "f_tests" not in result

    def test_unbalanced_design_is_refused(self):
        rows = [
            {"a": "a1", "b": "b1", "score": 0.50}, {"a": "a1", "b": "b1", "score": 0.52},
            {"a": "a1", "b": "b2", "score": 0.60}, {"a": "a1", "b": "b2", "score": 0.61},
            {"a": "a2", "b": "b1", "score": 0.60},
            {"a": "a2", "b": "b2", "score": 0.70},
        ]
        result = factorial_variance_decomposition(rows, "a", "b")
        assert result["status"] == "UNAVAILABLE"
        assert "balanced" in result["reason"]

    def test_missing_cell_is_reported_by_diagnostics(self):
        rows = [r for r in _balanced_2x2(ADDITIVE)
                if not (r["a"] == "a2" and r["b"] == "b2")]
        diag = factorial_diagnostics(rows, "a", "b")
        assert diag["complete"] is False
        assert diag["n_missing_cells"] == 1
        assert "a2|b2" in diag["missing_cells"]

    def test_interaction_screen_reports_ofat_honestly(self):
        rows = [
            {"a": "a1", "b": "b1", "score": 0.50},
            {"a": "a2", "b": "b1", "score": 0.60},
            {"a": "a1", "b": "b2", "score": 0.70},
        ]
        screen = interaction_screen(rows, "a", "b")
        assert screen["status"] == "UNAVAILABLE"
        assert screen["crossed_design"] is False
        assert "OFAT" in screen["reason"]

    def test_decomposition_is_deterministic(self):
        first = factorial_variance_decomposition(_balanced_2x2(ADDITIVE), "a", "b", n_boot=50, seed=7)
        second = factorial_variance_decomposition(_balanced_2x2(ADDITIVE), "a", "b", n_boot=50, seed=7)
        assert first == second

