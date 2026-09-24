"""Research-integrity tests (research Phase 19).

Cross-cutting guarantees, independent of any single module:
1. train/holdout partitions are always disjoint (no leakage),
2. estimators read ONLY train data (holdout mutations cannot move fits),
3. adaptive selection uses only information observed so far (no future data),
4. reported aggregates are reproducible from per-rep values (no fabrication),
5. deterministic seeds reproduce results bit-for-bit,
6. provenance fields are present on every research artifact.
"""

import copy

from apertus_eval_prep.adaptive import AdaptiveEvaluator
from apertus_eval_prep.heldout import (
    pairwise_estimates,
    split_config_keys,
)
from apertus_eval_prep.interaction import interaction_design

from tests.test_budget_replay import CANDIDATES, _replay_metrics

KEYS = [f"cfg{i:02d}" for i in range(16)]


# ---------------------------------------------------------------------------
# 1. partition disjointness across many budgets/seeds
# ---------------------------------------------------------------------------


def test_partitions_never_overlap_any_budget_seed():
    for budget in (1, 5, 8, 15):
        for seed in (0, 1, 7, 123):
            split = split_config_keys(KEYS, budget, seed=seed)
            assert not (set(split["train"]) & set(split["heldout"]))
            assert len(split["train"]) == budget
            assert len(split["train"]) + len(split["heldout"]) == len(KEYS)


def test_split_provenance_records_method_and_guard():
    split = split_config_keys(KEYS, 6, seed=0)
    assert "deterministic" in split["method"]
    assert "disjoint" in split["leakage_guard"]


# ---------------------------------------------------------------------------
# 2. estimator reads only train data
# ---------------------------------------------------------------------------


def test_holdout_mutation_cannot_change_p_hat():
    # p_hat is fitted on TRAIN only: mutating holdout scores must leave
    # every p_hat unchanged while holdout fractions DO change.
    train = [[0.9, 0.8, 0.3, 0.2], [0.7, 0.6, 0.4, 0.3]]
    hold = [[0.5, 0.6, 0.7, 0.8], [0.4, 0.5, 0.6, 0.7]]
    base = pairwise_estimates(train, hold)
    mutated = pairwise_estimates(train, [[0.4, 0.6, 0.9, 0.95],
                                         [0.5, 0.2, 0.85, 0.5]])
    p_base = {(p["a"], p["b"]): p["p_hat"] for p in base["pairs"]}
    p_mut = {(p["a"], p["b"]): p["p_hat"] for p in mutated["pairs"]}
    assert p_base == p_mut
    f_base = {(p["a"], p["b"]): p["holdout_fraction"] for p in base["pairs"]}
    f_mut = {(p["a"], p["b"]): p["holdout_fraction"] for p in mutated["pairs"]}
    assert f_base != f_mut


def test_train_mutation_changes_p_hat():
    # control for the previous test: mutating TRAIN does move the fit
    train = [[0.9, 0.8, 0.3, 0.2], [0.7, 0.6, 0.4, 0.3]]
    hold = [[0.5, 0.6, 0.7, 0.8], [0.4, 0.5, 0.6, 0.7]]
    base = pairwise_estimates(train, hold)
    changed = pairwise_estimates([[0.1, 0.8, 0.3, 0.2], [0.7, 0.6, 0.4, 0.3]], hold)
    p_base = {(p["a"], p["b"]): p["p_hat"] for p in base["pairs"]}
    p_new = {(p["a"], p["b"]): p["p_hat"] for p in changed["pairs"]}
    assert p_base != p_new


# ---------------------------------------------------------------------------
# 3. adaptive selection uses no future information
# ---------------------------------------------------------------------------


def _integrity_table():
    return {
        "big": {"c0": 0.90, "c1": 0.92, "c2": 0.88, "c3": 0.91},
        "mid": {"c0": 0.60, "c1": 0.63, "c2": 0.59, "c3": 0.61},
        "small": {"c0": 0.30, "c1": 0.33, "c2": 0.29, "c3": 0.31},
    }


def test_apertus_r_selection_is_independent_of_future_scores():
    # two tables identical except ('mid','c3'); selection sequences must be
    # identical up to and including the step where mid::c3 is observed.
    table_a = _integrity_table()
    table_b = copy.deepcopy(table_a)
    table_b["mid"]["c3"] = 0.05  # the ONLY difference
    seq_a, seq_b = [], []
    ev_a = AdaptiveEvaluator(CANDIDATES, budget=12, strategy="apertus_r", seed=0)
    ev_b = AdaptiveEvaluator(CANDIDATES, budget=12, strategy="apertus_r", seed=0)
    diverged_after = None
    for step in range(12):
        ca = ev_a.select_next()
        cb = ev_b.select_next()
        ka = f"{ca['model_id']}::{ca['config_key']}"
        kb = f"{cb['model_id']}::{cb['config_key']}"
        assert ka == kb, f"selection diverged at step {step} before c3 was seen"
        seq_a.append(ka)
        ev_a.observe(ca, table_a[ca["model_id"]][ca["config_key"]])
        ev_b.observe(cb, table_b[cb["model_id"]][cb["config_key"]])
        if ka == "mid::c3":
            diverged_after = step + 1
            break
    assert diverged_after is not None, "c3 was never measured"


def test_selection_sequence_deterministic_across_seeds_matches():
    table = _integrity_table()

    def _run(seed):
        ev = AdaptiveEvaluator(CANDIDATES, budget=6, strategy="apertus_r", seed=seed)
        seq = []
        while (c := ev.select_next()) is not None:
            seq.append(f"{c['model_id']}::{c['config_key']}")
            ev.observe(c, table[c["model_id"]][c["config_key"]])
        return seq

    assert _run(11) == _run(11)


# ---------------------------------------------------------------------------
# 4. reported aggregates are consistent with per-rep values (no fabrication)
# ---------------------------------------------------------------------------


def test_budget_curve_means_match_recomputed_replays():
    from statistics import mean as _mean

    table = _integrity_table()
    budget, n_rep, seed = 5, 4, 3
    strat = "random"
    # recompute the per-rep metrics independently
    per_rep = [
        _replay_metrics(table, CANDIDATES, budget, strat, seed=seed + rep)
        for rep in range(n_rep)
    ]
    expected = _mean(m["ranking_recovery"] for m in per_rep)
    from apertus_eval_prep.adaptive import budget_curves

    out = budget_curves(table, CANDIDATES, [budget], strategies=(strat,),
                        n_rep=n_rep, seed=seed)
    got = out["curves"][strat][budget]["values"]["ranking_recovery"]["mean"]
    assert abs(got - expected) < 1e-9


# ---------------------------------------------------------------------------
# 5. deterministic reproduction of research artifacts
# ---------------------------------------------------------------------------


def test_interaction_design_reproduces_bit_for_bit():
    study = {
        "control": {"backend": "hf", "quantization": "none", "seed": 0,
                    "prompt_id": "p0"},
        "models": ["m1", "m2"],
        "factors": {"prompt_id": ["p0", "p1"], "backend": ["hf", "vllm"]},
        "sampled": {"temperature": 0.7},
    }
    a = interaction_design(study, "prompt×backend", design="balanced",
                           seed=5, max_cells=3)
    b = interaction_design(study, "prompt×backend", design="balanced",
                           seed=5, max_cells=3)
    assert a == b
    assert a["seed"] == 5  # seed recorded in the artifact


# ---------------------------------------------------------------------------
# 6. provenance fields on research artifacts
# ---------------------------------------------------------------------------


def test_replay_metrics_records_what_was_measured():
    table = _integrity_table()
    m = _replay_metrics(table, CANDIDATES, 4, "apertus_r", seed=0)
    # n_measured is the provenance of exactly how much evidence the metrics use
    assert m["n_measured"] == 4
    assert m["evaluation_cost"] == 8.0  # default cost 2.0 per config

