"""Tests for held-out configuration experiments (research Phases 5-6, 9).

Verifies deterministic leakage-free splitting, calibration metrics on known
cases (including ties and empty inputs), tie-aware decision accuracy, and
the leave-one-model-out generalization probe. Synthetic matrices only.
"""

import math

import pytest

from apertus_eval_prep.heldout import (
    auroc,
    brier_score,
    budget_seed,
    coverage_fraction,
    expected_calibration_error,
    heldout_reliability_experiment,
    leave_one_model_out_experiment,
    leave_one_model_out_sweep,
    log_loss,
    pairwise_estimates,
    partition_matrix,
    run_heldout_experiments,
    split_config_keys,
)

KEYS = [f"cfg{i:02d}" for i in range(12)]


# ---------------------------------------------------------------------------
# splitting: deterministic, disjoint, budget-respecting
# ---------------------------------------------------------------------------


def test_split_is_deterministic():
    a = split_config_keys(KEYS, 4, seed=11)
    b = split_config_keys(KEYS, 4, seed=11)
    assert a["train"] == b["train"]
    assert a["heldout"] == b["heldout"]


def test_split_partitions_are_disjoint_and_complete():
    split = split_config_keys(KEYS, 5, seed=0)
    assert not (set(split["train"]) & set(split["heldout"]))
    assert sorted(split["train"] + split["heldout"]) == sorted(KEYS)
    assert split["n_train"] == 5 and split["n_heldout"] == 7
    assert split["n_total"] == 12


def test_split_budget_edges():
    full = split_config_keys(KEYS, len(KEYS), seed=0)
    assert full["heldout"] == []
    with pytest.raises(ValueError, match="budget"):
        split_config_keys(KEYS, 0)
    with pytest.raises(ValueError, match="exceeds"):
        split_config_keys(KEYS, len(KEYS) + 1)


def test_split_deduplicates_input_keys():
    split = split_config_keys(KEYS + KEYS, 6, seed=3)
    assert split["n_total"] == 12


# ---------------------------------------------------------------------------
# partition_matrix
# ---------------------------------------------------------------------------


def test_partition_matrix_matches_split_columns():
    split = split_config_keys(KEYS, 4, seed=2)
    matrix = [[float(i * 10 + c) for c in range(12)] for i in range(2)]
    train, hold = partition_matrix(matrix, split)
    lookup = {k: i for i, k in enumerate(KEYS)}
    for m in range(2):
        assert train[m] == [matrix[m][lookup[k]] for k in split["train"]]
        assert hold[m] == [matrix[m][lookup[k]] for k in split["heldout"]]


def test_partition_matrix_rejects_wrong_width():
    split = split_config_keys(KEYS, 4, seed=2)
    with pytest.raises(ValueError, match="columns"):
        partition_matrix([[0.0] * 5], split)


# ---------------------------------------------------------------------------
# calibration metrics: known values + edge cases
# ---------------------------------------------------------------------------


def test_brier_and_log_loss_known_values():
    assert brier_score([1.0, 0.0], [1, 0]) == 0.0
    assert brier_score([0.5], [1]) == 0.25
    assert brier_score([], [1]) is None
    ll = log_loss([1.0, 0.0], [1, 0])
    assert ll == 0.0
    assert log_loss([], [1]) is None
    # clipping prevents infinity
    assert log_loss([1.0], [0]) < 30.0


def test_ece_bins_and_empty():
    # perfectly calibrated two-point sample
    assert expected_calibration_error([1.0, 0.0], [1, 0]) == 0.0
    assert expected_calibration_error([], []) is None


def test_auroc_known_and_degenerate():
    assert auroc([0.9, 0.1], [1, 0]) == 1.0
    assert auroc([0.1, 0.9], [1, 0]) == 0.0
    assert auroc([0.5, 0.5], [1, 0]) == 0.5      # ties -> 0.5
    assert auroc([0.9], [1]) is None             # single class
    assert auroc([], []) is None


def test_coverage_fraction_ignores_none_bounds():
    cov = coverage_fraction([0.2, None, 0.0], [0.8, 0.5, 0.4], [0.5, 0.5, 0.5])
    assert cov == 0.5
    assert coverage_fraction([], [], []) is None


# ---------------------------------------------------------------------------
# pairwise estimates: ties, missing data
# ---------------------------------------------------------------------------


def test_pairwise_estimates_excludes_ties_from_decisions():
    # model 0 vs 1: train shows tie, win -> the tied config is EXCLUDED, so
    # p_hat = 1.0 over the single decidable config (tie is not a loss either)
    train = [
        [0.5, 0.9],
        [0.5, 0.7],
    ]
    hold = [
        [0.6, 0.8],
        [0.4, 0.7],
    ]
    est = pairwise_estimates(train, hold)
    pair = next(p for p in est["pairs"] if (p["a"], p["b"]) == (0, 1))
    assert pair["p_hat"] == 1.0  # tie excluded, remaining config is a win
    assert pair["n_train"] == 1  # one decidable train config
    assert pair["n_ties_train"] == 1
    assert pair["holdout_fraction"] == 1.0
    assert pair["n_ties_holdout"] == 0


def test_pairwise_estimates_requires_complete_configs():
    # config 1 has a missing value for model 1 -> excluded for that pair
    train = [
        [0.9, 0.8, 0.7],
        [0.5, None, 0.3],
    ]
    hold = [[0.9, 0.8, 0.7], [0.5, 0.2, 0.3]]
    est = pairwise_estimates(train, hold)
    pair = next(p for p in est["pairs"] if (p["a"], p["b"]) == (0, 1))
    assert pair["n_train"] == 2  # only complete configs


def test_pairwise_estimates_single_model_returns_empty():
    assert pairwise_estimates([[0.5, 0.6]], [None, None])["pairs"] == []


# ---------------------------------------------------------------------------
# heldout_reliability_experiment
# ---------------------------------------------------------------------------


def _matrix(seed: int = 0, n_models: int = 3, n_cfgs: int = 12):
    import random
    rng = random.Random(seed)
    return [
        [min(1.0, max(0.0, 0.3 + 0.2 * m + rng.uniform(-0.02, 0.02)))
         for _ in range(n_cfgs)]
        for m in range(n_models)
    ]


def test_heldout_experiment_reports_all_phase6_metrics():
    matrix = _matrix(seed=1)
    out = heldout_reliability_experiment(matrix, KEYS, budget=4, seed=0, n_boot=40)
    assert out["score_prediction_error_mae"] is not None
    assert out["ranking_recovery"]["kendall_tau"] is not None
    assert out["pairwise_decision_accuracy"] is not None
    cal = out["reliability_calibration"]
    for key in ("ece", "brier", "log_loss", "auroc"):
        assert cal[key] is not None
    assert out["reliability_estimation_error_mae"] is not None
    assert 0.0 <= out["ci_coverage"] <= 1.0
    assert out["split"]["n_train"] == 4
    # leakage guard recorded
    assert "train" in out["split"]["leakage_guard"]


def test_heldout_experiment_excludes_tie_pairs_from_accuracy():
    # Build the matrix FROM the deterministic split so the train partition
    # shows exactly 2 wins / 4 (p_hat = 0.5) and holdout 4 wins / 8 —
    # tie pairs are NOT decisions and accuracy must be undefined.
    split = split_config_keys(KEYS, 4, seed=0)
    row0, row1 = [None] * 12, [None] * 12
    for part, cols in (("train", split["train"]), ("heldout", split["heldout"])):
        for i, k in enumerate(cols):
            c = KEYS.index(k)
            if i % 2 == 0:               # alternate win/loss within partition
                row0[c], row1[c] = 0.9, 0.8
            else:
                row0[c], row1[c] = 0.8, 0.9
    matrix = [row0, row1]
    out = heldout_reliability_experiment(matrix, KEYS, budget=4, seed=0, n_boot=10)
    assert out["pairwise_decision_accuracy"] is None
    assert out["n_decidable_pairs"] == 0
    assert out["n_pairs_excluded_ties"] == 2
    # reliability error is still reported for tie pairs (it is not a decision)
    assert out["reliability_estimation_error_mae"] == 0.0


def test_heldout_experiment_identical_models_are_not_decisions():
    # strictly identical models: every config is a tie -> no decidable pair
    # exists, so decision accuracy / reliability error are unavailable (None),
    # never a fabricated 1.0.
    matrix = [[0.5] * 12, [0.5] * 12]
    out = heldout_reliability_experiment(matrix, KEYS, budget=4, seed=0, n_boot=10)
    assert out["pairwise_decision_accuracy"] is None
    assert out["reliability_estimation_error_mae"] is None
    assert out["n_pairs"] == 0
    assert out["n_decidable_pairs"] == 0
    assert out["score_prediction_error_mae"] == 0.0


def test_heldout_experiment_is_deterministic():
    matrix = _matrix(seed=3)
    a = heldout_reliability_experiment(matrix, KEYS, budget=5, seed=9, n_boot=30)
    b = heldout_reliability_experiment(matrix, KEYS, budget=5, seed=9, n_boot=30)
    assert a == b


def test_budget_sweep_uses_derived_seeds():
    matrix = _matrix(seed=4)
    out = run_heldout_experiments(matrix, KEYS, budgets=[4, 6], seed=0, n_boot=20)
    assert set(out["budgets"]) == {4, 6}
    b4 = out["budgets"][4]
    again = heldout_reliability_experiment(
        matrix, KEYS, budget=4, seed=budget_seed(0, 4), n_boot=20)
    assert b4 == again


def test_budget_seed_is_deterministic_and_injective_here():
    assert budget_seed(0, 10) == budget_seed(0, 10)
    assert budget_seed(0, 10) != budget_seed(0, 20)
    assert budget_seed(1, 10) != budget_seed(0, 10)


# ---------------------------------------------------------------------------
# leave-one-model-out (Phase 9B)
# ---------------------------------------------------------------------------


def test_lomo_hides_exactly_one_model_and_is_deterministic():
    matrix = _matrix(seed=5, n_models=4)
    out = leave_one_model_out_experiment(matrix, KEYS, budget=4, seed=2)
    again = leave_one_model_out_experiment(matrix, KEYS, budget=4, seed=2)
    assert out == again
    assert 0 <= out["hidden_model_index"] < 4
    assert out["n_visible_models"] == 3
    assert out["experiment_type"] == "leave_one_model_out"
    assert out["split"]["n_train"] == 4


def test_lomo_reports_ood_targets_without_prediction_claims():
    matrix = _matrix(seed=6, n_models=4)
    out = leave_one_model_out_experiment(matrix, KEYS, budget=4, seed=1)
    ood = out["out_of_distribution_hidden"]
    assert ood["stability"]["n_holdout_configs"] == out["split"]["n_heldout"]
    assert ood["stability"]["std_all_configs"] is not None
    assert len(ood["pair_flip_rates"]) == 3
    assert "not predicted" in ood["label"]
    assert out["power_note"]


def test_lomo_needs_three_models():
    out = leave_one_model_out_experiment([[0.5], [0.6]], ["c0"], budget=1, seed=0)
    assert out["hidden_model_index"] is None
    assert ">=3" in out["reason"]


def test_lomo_sweep_covers_budgets():
    matrix = _matrix(seed=7, n_models=3)
    out = leave_one_model_out_sweep(matrix, KEYS, budgets=[3, 6], seed=0)
    assert set(out["budgets"]) == {3, 6}
    assert all(b["experiment_type"] == "leave_one_model_out"
               for b in out["budgets"].values())
