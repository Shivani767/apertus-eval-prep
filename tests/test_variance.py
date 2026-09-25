"""Tests for factorial variance decomposition (research Phase 3).

Verifies the guarded two-way decomposition on synthetic data with known
effect structure, plus pathological-input policy (no forced ANOVA).
"""

import math

from apertus_eval_prep.variance import (
    factorial_diagnostics,
    factorial_variance_decomposition,
    interaction_screen,
)


def _rows_from_cells(cells: dict[tuple[str, str], list[float]]) -> list[dict]:
    rows = []
    for (a, b), vals in cells.items():
        for v in vals:
            rows.append({"a": a, "b": b, "score": v})
    return rows


def test_balanced_two_way_exact_partition():
    # additive model, no interaction: SS_A + SS_B + SS_AB + SS_E == SS_total
    cells = {}
    for a, da in (("l0", 0.0), ("l1", 1.0)):
        for b, db in (("m0", 0.0), ("m1", 2.0)):
            cells[(a, b)] = [3.0 + da + db + e for e in (0.1, -0.1)]
    rows = _rows_from_cells(cells)
    out = factorial_variance_decomposition(rows, "a", "b")
    assert out["status"] == "MEASURED"
    ss = out["sums_of_squares"]
    total = ss["ss_a"] + ss["ss_b"] + ss["ss_ab"] + ss["ss_e"]
    assert math.isclose(total, ss["ss_total"], rel_tol=1e-6)
    # additive design -> interaction ~ 0, residual tiny
    assert out["variance_fractions"]["interaction"] < 0.01
    assert out["variance_fractions"]["residual"] < 0.05
    assert out["variance_fractions"]["factor_b"] > out["variance_fractions"]["factor_a"]


def test_interaction_present_is_detected():
    # interaction only, no main effects: cell pattern [[0,1],[1,0]]
    cells = {
        ("l0", "m0"): [0.0, 0.0], ("l0", "m1"): [1.0, 1.0],
        ("l1", "m0"): [1.0, 1.0], ("l1", "m1"): [0.0, 0.0],
    }
    rows = _rows_from_cells(cells)
    out = factorial_variance_decomposition(rows, "a", "b")
    assert out["status"] == "MEASURED"
    assert out["variance_fractions"]["interaction"] > 0.5
    assert out["variance_fractions"]["factor_a"] < 0.01
    assert out["variance_fractions"]["factor_b"] < 0.01


def test_effect_sizes_match_fractions():
    cells = {
        ("l0", "m0"): [1.0, 2.0], ("l0", "m1"): [3.0, 4.0],
        ("l1", "m0"): [5.0, 6.0], ("l1", "m1"): [7.0, 8.0],
    }
    rows = _rows_from_cells(cells)
    out = factorial_variance_decomposition(rows, "a", "b")
    for key in ("factor_a", "factor_b", "interaction", "residual"):
        f = out["variance_fractions"][key]
        o2 = out["effect_sizes_omega2_pct"][key]
        assert math.isclose(o2, round(f * 100, 4), abs_tol=0.001)


def test_variance_fractions_sum_to_one():
    cells = {
        ("l0", "m0"): [0.0, 0.0], ("l0", "m1"): [1.0, 1.0],
        ("l1", "m0"): [1.0, 1.0], ("l1", "m1"): [0.0, 0.0],
    }
    rows = _rows_from_cells(cells)
    out = factorial_variance_decomposition(rows, "a", "b")
    frac = out["variance_fractions"]
    total = sum(v for v in frac.values() if v is not None)
    assert math.isclose(total, 1.0, rel_tol=1e-6)


def test_bootstrap_cis_are_seeded_and_stable():
    cells = {
        ("l0", "m0"): [1.0, 2.0], ("l0", "m1"): [3.0, 4.0],
        ("l1", "m0"): [5.0, 6.0], ("l1", "m1"): [7.0, 8.0],
    }
    rows = _rows_from_cells(cells)
    a = factorial_variance_decomposition(rows, "a", "b", n_boot=50, seed=5)
    b = factorial_variance_decomposition(rows, "a", "b", n_boot=50, seed=5)
    assert a["bootstrap_ci95"] == b["bootstrap_ci95"]
    ci = a["bootstrap_ci95"]["factor_a"]
    lo, hi = ci
    assert 0.0 <= lo <= a["variance_fractions"]["factor_a"] <= hi <= 1.0
    assert a["bootstrap_ci95"]["n_boot"] == 50 and a["bootstrap_ci95"]["seed"] == 5


# ---------------------------------------------------------------------------
# guarded policy: pathological inputs must NOT be forced into ANOVA
# ---------------------------------------------------------------------------


def test_single_level_per_axis_unavailable():
    cells = {("l0", "m0"): [1.0, 2.0]}
    rows = _rows_from_cells(cells)
    out = factorial_variance_decomposition(rows, "a", "b")
    assert out["status"] == "UNAVAILABLE"
    assert "2 levels" in out["reason"]


def test_incomplete_design_unavailable():
    # 2x3 design with one missing cell: >= 4 crossed cells but incomplete
    rows = [
        {"a": "l0", "b": "m0", "score": 1.0},
        {"a": "l0", "b": "m1", "score": 2.0},
        {"a": "l0", "b": "m2", "score": 3.0},
        {"a": "l1", "b": "m0", "score": 4.0},
        {"a": "l1", "b": "m1", "score": 5.0},
        # (l1, m2) deliberately absent
    ]
    out = factorial_variance_decomposition(rows, "a", "b")
    assert out["status"] == "UNAVAILABLE"
    assert "balanced" in out["reason"]
    assert out["diagnostics"]["n_missing_cells"] == 1
    assert out["diagnostics"]["missing_cells"] == ["l1|m2"]


def test_unbalanced_design_unavailable():
    cells = {
        ("l0", "m0"): [1.0, 2.0], ("l0", "m1"): [2.0],
        ("l1", "m0"): [3.0, 4.0], ("l1", "m1"): [4.0, 6.0],
    }
    rows = _rows_from_cells(cells)
    out = factorial_variance_decomposition(rows, "a", "b")
    assert out["status"] == "UNAVAILABLE"
    assert out["diagnostics"]["balanced"] is False


def test_zero_variance_returns_zero_fractions_not_crash():
    cells = {
        ("l0", "m0"): [1.0, 1.0], ("l0", "m1"): [1.0, 1.0],
        ("l1", "m0"): [1.0, 1.0], ("l1", "m1"): [1.0, 1.0],
    }
    rows = _rows_from_cells(cells)
    out = factorial_variance_decomposition(rows, "a", "b")
    assert out["status"] == "MEASURED"
    assert out["sums_of_squares"]["ss_total"] == 0.0
    assert all(v is None for v in out["variance_fractions"].values())


def test_missing_scores_skipped_never_imputed():
    # A None score is skipped; skipping can leave a BALANCED 1-rep design,
    # which is then legitimately MEASURED (never imputed).
    rows = [
        {"a": "l0", "b": "m0", "score": 1.0},
        {"a": "l0", "b": "m0", "score": None},   # skipped
        {"a": "l0", "b": "m1", "score": 3.0},
        {"a": "l1", "b": "m0", "score": 5.0},
        {"a": "l1", "b": "m1", "score": 7.0},
        {"a": "l1", "b": "m1"},                  # no score key
    ]
    out = factorial_variance_decomposition(rows, "a", "b")
    assert out["status"] == "MEASURED"
    assert out["n_observations"] == 4


def test_missing_scores_leading_to_unbalanced_design_are_guarded():
    rows = [
        {"a": "l0", "b": "m0", "score": 1.0},
        {"a": "l0", "b": "m0", "score": 2.0},    # 2 reps here...
        {"a": "l0", "b": "m1", "score": 3.0},    # ...1 rep elsewhere
        {"a": "l1", "b": "m0", "score": 5.0},
        {"a": "l1", "b": "m1", "score": 7.0},
    ]
    out = factorial_variance_decomposition(rows, "a", "b")
    assert out["status"] == "UNAVAILABLE"
    assert out["diagnostics"]["balanced"] is False
    assert out["diagnostics"]["min_reps"] == 1
    assert out["diagnostics"]["max_reps"] == 2


def test_diagnostics_reports_missing_cells():
    cells = {
        ("l0", "m0"): [1.0], ("l0", "m1"): [2.0], ("l1", "m0"): [3.0],
    }
    diag = factorial_diagnostics(_rows_from_cells(cells), "a", "b")
    assert diag["missing_cells"] == ["l1|m1"]
    assert diag["complete"] is False


def test_interaction_screen_requires_crossed_design():
    # pure OFAT: a varies while b fixed
    ofat = [
        {"a": "l0", "b": "m0", "score": 1.0},
        {"a": "l1", "b": "m0", "score": 2.0},
    ]
    out = interaction_screen(ofat, "a", "b")
    assert out["status"] == "UNAVAILABLE"
    assert out["crossed_design"] is False
    assert "factorial" in out["reason"]
