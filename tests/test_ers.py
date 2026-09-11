"""Tests for the Evaluation Reliability Score (ERS). Synthetic matrices only."""

import pytest

from apertus_eval_prep.reliability import (
    DEFAULT_WEIGHTS,
    ers_ablation,
    evaluation_reliability_score,
)

# well-separated models, stable across 3 configs -> high reliability
SEPARATED = [
    [0.90, 0.91, 0.90],
    [0.60, 0.61, 0.60],
    [0.30, 0.31, 0.30],
]
# near-tied models, config-sensitive -> low reliability
FRAGILE = [
    [0.50, 0.44, 0.56],
    [0.49, 0.55, 0.43],
]


def test_separated_matrix_scores_high():
    out = evaluation_reliability_score(SEPARATED, n_per_cell=800, seed=0)
    assert out["ers"] is not None and out["ers"] > 0.7
    assert out["components"]["ci_separation"] == 1.0  # n=2400, huge gaps
    assert out["components"]["bootstrap_tau"] == 1.0
    assert out["n_components"] == 3  # no seed_scores -> seed_stability excluded
    assert "seed_stability" not in out["components_used"]
    assert out["provisional"] is True


def test_fragile_matrix_scores_lower():
    hi = evaluation_reliability_score(SEPARATED, n_per_cell=800, n_boot=200)
    lo = evaluation_reliability_score(FRAGILE, n_per_cell=800, n_boot=200)
    assert lo["ers"] < hi["ers"]
    assert lo["components"]["ci_separation"] < hi["components"]["ci_separation"]
    assert lo["components"]["config_stability"] < hi["components"]["config_stability"]


def test_missing_n_per_cell_excludes_component():
    out = evaluation_reliability_score(SEPARATED, n_per_cell=None, n_boot=200)
    assert out["components"]["ci_separation"] is None
    assert "ci_separation" not in out["components_used"]
    assert out["n_components"] == 2
    assert out["ers"] is not None


def test_degenerate_identical_models():
    same = [[0.5, 0.5, 0.5], [0.5, 0.5, 0.5]]
    out = evaluation_reliability_score(same, n_per_cell=100, n_boot=50)
    assert out["components"]["config_stability"] is None  # between-model std = 0
    assert out["ers"] is not None  # other components still defined


def test_seed_scores_added_and_validated():
    seeds = [[0.90, 0.91, 0.89], [0.60, 0.59, 0.61], [0.30, 0.31, 0.30]]
    without = evaluation_reliability_score(SEPARATED, n_per_cell=800, n_boot=100)
    with_s = evaluation_reliability_score(
        SEPARATED, n_per_cell=800, seed_scores=seeds, n_boot=100)
    assert with_s["n_components"] == 4
    assert with_s["components"]["seed_stability"] > 0.9
    # ERS is a weighted mean in [0,1]: adding a 0.96 component to a ~0.996
    # average slightly DILUTES it — it must stay close, not grow monotonically.
    assert abs(with_s["ers"] - without["ers"]) < 0.05


def test_weight_validation():
    with pytest.raises(ValueError, match="unknown"):
        evaluation_reliability_score(SEPARATED, weights={"magic": 1.0})
    with pytest.raises(ValueError, match="positive"):
        evaluation_reliability_score(SEPARATED, weights={"ci_separation": 0.0})
    with pytest.raises(ValueError, match="positive"):
        evaluation_reliability_score(SEPARATED, weights={})
    # renormalization: equal weights give the plain mean of components
    out = evaluation_reliability_score(
        SEPARATED, n_per_cell=800, n_boot=100,
        weights={k: 1.0 for k in DEFAULT_WEIGHTS if k != "seed_stability"})
    comps = [out["components"][k] for k in out["components_used"]]
    # ers is rounded to 4dp; compare with matching tolerance
    assert abs(out["ers"] - sum(comps) / len(comps)) < 1e-4


def test_ablation_shows_weight_sensitivity():
    abl = ers_ablation(SEPARATED, n_per_cell=800, n_boot=100)
    assert set(abl["drop_one"]) == {"bootstrap_tau", "ci_separation",
                                    "config_stability"}
    for comp, d in abl["drop_one"].items():
        assert d["ers_without"] is not None
        # dropping the top-weight component (ci_separation=1.0) lowers ERS
    assert abl["drop_one"]["ci_separation"]["delta"] < 0