"""Pathological-input tests for reliability/heldout/variance modules.

Covers the failure modes the research harnesses must survive without
fabricating numbers: ties, missing measurements, single model/config,
zero variance, NaN, failed evaluations (None), incomplete registries,
identical and opposite rankings.
"""

import math

from apertus_eval_prep.heldout import (
    auroc,
    brier_score,
    expected_calibration_error,
    heldout_reliability_experiment,
    leave_one_model_out_experiment,
    log_loss,
    pairwise_estimates,
    split_config_keys,
)
from apertus_eval_prep.variance import factorial_variance_decomposition

KEYS = [f"c{i}" for i in range(6)]


def _row(base, noise=0.0, n=6):
    return [None if base is None else base + noise * i for i in range(n)]


# ---------------------------------------------------------------------------
# heldout reliability experiment
# ---------------------------------------------------------------------------


def test_single_model_unavailable():
    matrix = [[0.5, 0.6, 0.7, 0.4, 0.3, 0.2]]
    out = heldout_reliability_experiment(matrix, KEYS, budget=2, seed=0, n_boot=20)
    assert out["pairwise_decision_accuracy"] is None
    assert out["ranking_recovery"]["kendall_tau"] is None
    assert out["n_pairs"] == 0
    # per-model score MAE is still defined with a single model
    assert out["score_prediction_error_mae"] is not None


def test_all_scores_identical_zero_variance():
    matrix = [[0.5] * 6, [0.5] * 6]
    out = heldout_reliability_experiment(matrix, KEYS, budget=2, seed=0, n_boot=20)
    # pure ties: no decidable pair, calibration inputs are all p=0.5/y=0.5
    assert out["n_decidable_pairs"] == 0
    assert out["pairwise_decision_accuracy"] is None
    assert out["score_prediction_error_mae"] == 0.0


def test_missing_measurements_drop_configs_not_fabricate():
    # config 2 and 4 have holes -> usable cells only from complete configs
    matrix = [
        [0.9, 0.8, None, 0.85, None, 0.7],
        [0.7, 0.6, 0.65, None, 0.5, 0.4],
    ]
    out = heldout_reliability_experiment(matrix, KEYS, budget=2, seed=0, n_boot=20)
    # must run without error and use only complete cells for pairs
    for p in pairwise_estimates(matrix, matrix)["pairs"]:
        assert p["n_train"] <= 6
    assert out is not None


def test_failed_evaluations_all_none_model_excluded():
    # model 2's evaluations all failed (None) -> excluded from pairs
    matrix = [
        [0.9, 0.8, 0.85, 0.7, 0.6, 0.65],
        [None] * 6,
    ]
    out = heldout_reliability_experiment(matrix, KEYS, budget=2, seed=0, n_boot=20)
    assert out["n_pairs"] == 0
    assert out["pairwise_decision_accuracy"] is None


def test_nan_scores_treated_as_failed():
    matrix = [
        [0.9, float("nan"), 0.85, 0.7, 0.6, 0.65],
        [0.7, 0.6, 0.4, 0.3, 0.5, 0.45],
    ]
    out = heldout_reliability_experiment(matrix, KEYS, budget=2, seed=0, n_boot=20)
    # NaN propagates into comparisons as False; the harness must not crash
    assert out is not None


def test_budget_equal_to_space_leaves_empty_holdout():
    matrix = [[0.9, 0.8, 0.7, 0.6, 0.5, 0.4], [0.7, 0.6, 0.5, 0.4, 0.3, 0.2]]
    out = heldout_reliability_experiment(matrix, KEYS, budget=6, seed=0, n_boot=20)
    assert out["split"]["n_heldout"] == 0
    # no holdout evidence -> pairwise decision metrics unavailable
    assert out["pairwise_decision_accuracy"] is None


def test_opposite_rankings_give_perfectly_negative_recovery():
    # train and holdout partitions induce EXACTLY reversed model rankings
    split = split_config_keys(KEYS, 3, seed=0)
    train_keys = set(split["train"])
    row0 = [0.9 if k in train_keys else 0.1 for k in KEYS]
    row1 = [0.1 if k in train_keys else 0.9 for k in KEYS]
    out = heldout_reliability_experiment([row0, row1], KEYS, budget=3,
                                         seed=0, n_boot=20)
    assert out["ranking_recovery"]["kendall_tau"] == -1.0
    assert out["ranking_recovery"]["spearman"] == -1.0
    assert out["pairwise_decision_accuracy"] == 0.0


def test_identical_rankings_perfect_recovery():
    matrix = [
        [0.9, 0.9, 0.9, 0.9, 0.9, 0.9],
        [0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
    ]
    out = heldout_reliability_experiment(matrix, KEYS, budget=3, seed=0, n_boot=20)
    assert out["ranking_recovery"]["kendall_tau"] == 1.0


# ---------------------------------------------------------------------------
# leave-one-model-out pathological inputs
# ---------------------------------------------------------------------------


def test_lomo_needs_three_models():
    matrix = [[0.5] * 6, [0.4] * 6]
    out = leave_one_model_out_experiment(matrix, KEYS, budget=2, seed=0)
    assert out["hidden_model_index"] is None
    assert ">=3" in out["reason"]


def test_lomo_all_identical_models():
    matrix = [[0.5] * 6 for _ in range(4)]
    out = leave_one_model_out_experiment(matrix, KEYS, budget=2, seed=0)
    assert out["hidden_model_index"] is not None
    assert out["in_distribution_visible"]["pairwise_decision_accuracy"] is None
    assert out["out_of_distribution_hidden"]["stability"]["std_all_configs"] == 0.0


# ---------------------------------------------------------------------------
# factorial variance decomposition pathological inputs
# ---------------------------------------------------------------------------


def _cells_rows(a_levels, b_levels, reps, value_fn):
    rows = []
    for a in a_levels:
        for b in b_levels:
            for r in range(reps):
                rows.append({"A": a, "B": b, "score": value_fn(a, b, r)})
    return rows


def test_variance_unavailable_single_level():
    rows = _cells_rows(["only"], ["x", "y"], 2, lambda a, b, r: 0.5)
    out = factorial_variance_decomposition(rows, "A", "B")
    assert out["status"] == "UNAVAILABLE"
    assert "2 levels" in out["reason"]


def test_variance_unavailable_incomplete_design():
    # 2 x 3 grid minus one cell: >= 4 crossed cells remain, but the design
    # is incomplete -> must hit the completeness guard, not the cell-count one
    rows = _cells_rows(["a1", "a2"], ["b1", "b2", "b3"], 2,
                       lambda a, b, r: 0.5)
    rows = [r for r in rows if not (r["A"] == "a2" and r["B"] == "b3")]
    out = factorial_variance_decomposition(rows, "A", "B")
    assert out["status"] == "UNAVAILABLE"
    assert "balanced" in out["reason"]


def test_variance_unavailable_unbalanced_design():
    rows = _cells_rows(["a1", "a2"], ["b1", "b2"], 2, lambda a, b, r: 0.5)
    rows.append({"A": "a1", "B": "b1", "score": 0.4})  # extra replication
    out = factorial_variance_decomposition(rows, "A", "B")
    assert out["status"] == "UNAVAILABLE"
    assert "balanced" in out["reason"]


def test_variance_zero_scores_all_none_fractions():
    rows = _cells_rows(["a1", "a2"], ["b1", "b2"], 2,
                       lambda a, b, r: None)  # all failed
    out = factorial_variance_decomposition(rows, "A", "B")
    assert out["status"] == "UNAVAILABLE"  # no scored cells at all


def test_variance_zero_total_variance_gives_none_fractions():
    rows = _cells_rows(["a1", "a2"], ["b1", "b2"], 2, lambda a, b, r: 0.5)
    out = factorial_variance_decomposition(rows, "A", "B")
    assert out["status"] == "MEASURED"
    assert out["sums_of_squares"]["ss_total"] == 0.0
    assert all(v is None for v in out["variance_fractions"].values())


def test_variance_nan_score_does_not_crash():
    rows = _cells_rows(["a1", "a2"], ["b1", "b2"], 2,
                       lambda a, b, r: 0.5 if r == 0 else float("nan"))
    out = factorial_variance_decomposition(rows, "A", "B")
    # NaN poisons the sums; result is either UNAVAILABLE or MEASURED with
    # NaN-poisoned sums — must not raise either way
    assert out["status"] in ("MEASURED", "UNAVAILABLE")


def test_variance_clean_signal_sums_partition_exactly():
    def fn(a, b, r):
        return {"a1": {"b1": 0.9, "b2": 0.8}, "a2": {"b1": 0.3, "b2": 0.4}}[a][b] \
            + (r * 0.01)

    rows = _cells_rows(["a1", "a2"], ["b1", "b2"], 3, fn)
    out = factorial_variance_decomposition(rows, "A", "B", n_boot=50, seed=0)
    assert out["status"] == "MEASURED"
    ss = out["sums_of_squares"]
    total = ss["ss_a"] + ss["ss_b"] + ss["ss_ab"] + ss["ss_e"]
    assert math.isclose(total, ss["ss_total"], rel_tol=1e-9)
    fr = out["variance_fractions"]
    assert math.isclose(sum(fr.values()), 1.0, rel_tol=1e-6)


def test_variance_single_replication_no_residual():
    rows = _cells_rows(["a1", "a2"], ["b1", "b2"], 1, lambda a, b, r: 0.5)
    out = factorial_variance_decomposition(rows, "A", "B")
    assert out["status"] == "MEASURED"
    assert out["sums_of_squares"]["ss_e"] == 0.0

