"""Tests for budget-curve replay (research Phases 7-8).

Known synthetic score tables only; verifies fair budget accounting across
strategies, determinism, tie-aware decision accuracy, cost accounting, and
that the harness reports (never claims) strategy performance.
"""

import pytest

from apertus_eval_prep.adaptive import (
    STRATEGIES,
    _replay_metrics,
    budget_curves,
    compare_strategies,
)

MODELS = ["big", "mid", "small"]
CONFIGS = [f"c{i}" for i in range(4)]
CANDIDATES = [
    {"model_id": m, "config_key": c, "estimated_cost": 2.0}
    for m in MODELS
    for c in CONFIGS
]


def _table():
    # clear ranking (big > mid > small); per-config spread so ranking from a
    # subset is not trivially identical to the full-table ranking.
    return {
        "big": {"c0": 0.90, "c1": 0.92, "c2": 0.88, "c3": 0.91},
        "mid": {"c0": 0.60, "c1": 0.63, "c2": 0.59, "c3": 0.61},
        "small": {"c0": 0.30, "c1": 0.33, "c2": 0.29, "c3": 0.31},
    }


def test_replay_metrics_budget_accounting_fair():
    # every strategy measures exactly `budget` configurations
    table = _table()
    for strat in STRATEGIES:
        m = _replay_metrics(table, CANDIDATES, budget=5, strategy=strat, seed=0)
        assert m["n_measured"] == 5
        # cost = 2.0 per measured config
        assert m["evaluation_cost"] == 10.0


def test_replay_metrics_deterministic_per_seed():
    table = _table()
    a = _replay_metrics(table, CANDIDATES, 5, "random", seed=4)
    b = _replay_metrics(table, CANDIDATES, 5, "random", seed=4)
    assert a == b


def test_replay_metrics_all_fields_present():
    table = _table()
    m = _replay_metrics(table, CANDIDATES, 6, "apertus_r", seed=0)
    for key in ("ranking_recovery", "pairwise_decision_accuracy",
                "score_error_mae", "reliability_error_mae", "kendall_tau",
                "evaluation_cost", "n_measured"):
        assert key in m, key


def test_replay_metrics_perfect_recovery_with_clear_signal():
    # constant per-model scores -> any measured subset recovers the ranking
    table = {
        "big": {c: 0.90 for c in CONFIGS},
        "mid": {c: 0.60 for c in CONFIGS},
        "small": {c: 0.30 for c in CONFIGS},
    }
    for strat in ("random", "ofat", "apertus_r"):
        m = _replay_metrics(table, CANDIDATES, 12, strat, seed=0)
        assert m["n_measured"] == 12
        assert m["ranking_recovery"] == 1.0
        assert m["pairwise_decision_accuracy"] == 1.0
        assert m["score_error_mae"] == 0.0
        assert m["reliability_error_mae"] == 0.0


def test_replay_metrics_small_budget_may_measure_few_models():
    # with budget < n_models x 1 config, only a subset of models may be
    # measured; the harness must not fabricate accuracy for unseen pairs.
    table = _table()
    m = _replay_metrics(table, CANDIDATES, 2, "random", seed=0)
    assert m["n_measured"] == 2
    n_models_measured = 2 if m["pairwise_decision_accuracy"] is not None else 1
    assert m["kendall_tau"] is None or n_models_measured >= 2


def test_replay_metrics_ties_are_not_decisions():
    # all models identical -> every pairwise comparison is a tie on both
    # sides -> accuracy is None (undefined), never spuriously 1.0
    table = {m: {c: 0.5 for c in CONFIGS} for m in MODELS}
    m = _replay_metrics(table, CANDIDATES, 6, "random", seed=0)
    assert m["pairwise_decision_accuracy"] is None


def test_replay_metrics_empty_candidates_rejected():
    # nothing to measure -> the evaluator refuses the configuration outright
    with pytest.raises(ValueError, match="candidates"):
        _replay_metrics({"x": {}}, [], 1, "random", seed=0)


# ---------------------------------------------------------------------------
# budget_curves harness
# ---------------------------------------------------------------------------


def test_budget_curves_structure_and_fair_budgets():
    table = _table()
    out = budget_curves(table, CANDIDATES, budgets=[2, 5],
                        strategies=("random", "ofat", "apertus_r"),
                        n_rep=3, seed=0)
    assert out["budgets"] == [2, 5]
    assert set(out["curves"]) == {"random", "ofat", "apertus_r"}
    for strat, curve in out["curves"].items():
        for b, point in curve.items():
            assert point["n_rep"] == 3
            for metric, stats in point["values"].items():
                assert "mean" in stats and "ci_lo" in stats and "ci_hi" in stats
                assert stats["ci_lo"] <= stats["mean"] <= stats["ci_hi"]
            # fair budget: every strategy measures exactly b configs
            if "n_measured" in point["values"]:
                assert point["values"]["n_measured"]["mean"] == float(b)
            if "evaluation_cost" in point["values"]:
                assert point["values"]["evaluation_cost"]["mean"] == 2.0 * b


def test_budget_curves_deterministic():
    table = _table()
    a = budget_curves(table, CANDIDATES, [3], n_rep=2, seed=1)
    b = budget_curves(table, CANDIDATES, [3], n_rep=2, seed=1)
    assert a == b


def test_budget_curves_unknown_strategy_rejected():
    with pytest.raises(ValueError, match="strategy"):
        budget_curves(_table(), CANDIDATES, [3], strategies=("oracle",))


def test_budget_curves_monotone_information_never_hurts_recovery():
    # with a clean signal, more budget should not DEGRADE mean recovery
    # (an empirical sanity check on the harness, not a theorem)
    table = _table()
    out = budget_curves(table, CANDIDATES, budgets=[2, 8],
                        strategies=("random", "apertus_r"), n_rep=4, seed=0)
    for strat in ("random", "apertus_r"):
        lo = out["curves"][strat][2]["values"]["ranking_recovery"]["mean"]
        hi = out["curves"][strat][8]["values"]["ranking_recovery"]["mean"]
        assert hi >= lo - 0.05


# ---------------------------------------------------------------------------
# compare_strategies harness
# ---------------------------------------------------------------------------


def test_compare_strategies_reports_without_claiming():
    out = compare_strategies(_table(), CANDIDATES, budget=4,
                             strategies=("random", "uncertainty"),
                             n_rep=3, seed=0)
    assert set(out) == {"random", "uncertainty"}
    for strat, r in out.items():
        assert r["budget"] == 4
        assert r["n_rep"] == 3
        assert 0.0 <= r["mean_agreement"] <= 1.0


def test_compare_strategies_deterministic():
    a = compare_strategies(_table(), CANDIDATES, 4, ("random",), n_rep=2, seed=5)
    b = compare_strategies(_table(), CANDIDATES, 4, ("random",), n_rep=2, seed=5)
    assert a == b


def test_all_registered_strategies_run_end_to_end():
    table = _table()
    out = budget_curves(table, CANDIDATES, budgets=[4],
                        strategies=list(STRATEGIES), n_rep=1, seed=0)
    assert set(out["curves"]) == set(STRATEGIES)

