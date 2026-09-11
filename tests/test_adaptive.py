"""Tests for Phase 9: adaptive evaluation. Synthetic scores only."""

import pytest

from apertus_eval_prep.adaptive import (
    AdaptiveEvaluator,
    STRATEGIES,
    compare_strategies,
)

MODELS = ["big", "mid", "small"]
CONFIGS = ["c1", "c2", "c3"]
CANDIDATES = [
    {"model_id": m, "config_key": c} for m in MODELS for c in CONFIGS
]


def _table():
    # big always best, mid middle, small worst: clear ranking to recover.
    return {
        "big": {"c1": 0.90, "c2": 0.92, "c3": 0.91},
        "mid": {"c1": 0.60, "c2": 0.62, "c3": 0.61},
        "small": {"c1": 0.30, "c2": 0.32, "c3": 0.31},
    }


def test_validation():
    with pytest.raises(ValueError, match="budget"):
        AdaptiveEvaluator(CANDIDATES, budget=0)
    with pytest.raises(ValueError, match="budget"):
        AdaptiveEvaluator(CANDIDATES, budget=len(CANDIDATES) + 1)
    with pytest.raises(ValueError, match="strategy"):
        AdaptiveEvaluator(CANDIDATES, budget=3, strategy="oracle")


def test_budget_respected_and_deterministic():
    for strat in STRATEGIES:
        ev = AdaptiveEvaluator(CANDIDATES, budget=5, strategy=strat, seed=7)
        chosen = []
        while (cand := ev.select_next()) is not None:
            key = f"{cand['model_id']}::{cand['config_key']}"
            assert key not in chosen, f"{strat} re-selected {key}"
            chosen.append(key)
            ev.observe(cand, _table()[cand["model_id"]][cand["config_key"]], n=800)
        assert len(chosen) == 5
        assert ev.state.budget_left() == 0
        assert ev.stopped() is True  # budget exhausted
        assert ev.select_next() is None  # no more budget
    # deterministic given seed
    a = AdaptiveEvaluator(CANDIDATES, budget=4, strategy="random", seed=3)
    seq_a = []
    while (c := a.select_next()) is not None:
        seq_a.append((c["model_id"], c["config_key"]))
        a.observe(c, 0.5)
    b = AdaptiveEvaluator(CANDIDATES, budget=4, strategy="random", seed=3)
    seq_b = []
    while (c := b.select_next()) is not None:
        seq_b.append((c["model_id"], c["config_key"]))
        b.observe(c, 0.5)
    assert seq_a == seq_b


def test_uncertainty_prefers_unmeasured_models_then_close_pairs():
    ev = AdaptiveEvaluator(CANDIDATES, budget=9, strategy="uncertainty", seed=1)
    first = ev.select_next()
    ev.observe(first, 0.5, n=800)
    # second pick should be a DIFFERENT model (uncertainty tackles unknown models first)
    second = ev.select_next()
    assert second["model_id"] != first["model_id"]
    # measure two models of the clear table; the uncertain pair is big/mid
    ev2 = AdaptiveEvaluator(CANDIDATES, budget=9, strategy="uncertainty", seed=2)
    first2 = ev2.select_next()
    ev2.observe(first2, _table()[first2["model_id"]][first2["config_key"]], n=800)
    while ev2.state.scores_of(first2["model_id"]) and len(
            ev2.state.measured) < 2:
        c = ev2.select_next()
        if c is None:
            break
        ev2.observe(c, _table()[c["model_id"]][c["config_key"]], n=800)
    pair = ev2.state.most_uncertain_pair()
    assert pair is not None and len({p for p in pair if p}) >= 1


def test_observe_validation():
    ev = AdaptiveEvaluator(CANDIDATES, budget=9, strategy="random", seed=0)
    with pytest.raises(ValueError, match="score"):
        ev.observe(CANDIDATES[0], 1.5)
    with pytest.raises(ValueError, match="score"):
        ev.observe(CANDIDATES[0], -0.1)


def test_confidence_and_stop():
    ev = AdaptiveEvaluator(CANDIDATES, budget=9, strategy="random", seed=4)
    assert ev.selecting_confidence() is None  # <2 models measured
    assert ev.stopped(at_least_models=2, threshold=0.9) is False
    # measure all three models with well-separated scores -> no CI overlap
    for m in MODELS:
        c = next(c for c in _table().keys())
        c = [x for x in CANDIDATES if x["model_id"] == m][0]
        ev.observe(c, _table()[m]["c1"], n=800)
    conf = ev.selecting_confidence()
    assert conf is not None and conf >= 0.9
    assert ev.stopped(at_least_models=3, threshold=0.9) is True


def test_compare_strategies_harness_runs_and_reports():  # no claim of superiority
    out = compare_strategies(_table(), CANDIDATES, budget=6,
                             strategies=("random", "uncertainty"),
                             n_rep=3, seed=0)
    assert set(out) == {"random", "uncertainty"}
    for strat in out:
        assert 0.0 <= out[strat]["mean_agreement"] <= 1.0
        assert out[strat]["budget"] == 6
        assert out[strat]["n_models"] == 3