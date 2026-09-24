"""Held-out configuration experiments (research Phases 5-6).

Deterministic, leakage-free train/holdout splitting of the configuration
space, plus a validation harness for reliability estimators:

    observed (train) configs  -> fit estimator (pairwise P(A>B | C ~ P_train(C)),
                                 ERS components)
    hidden (test) configs     -> compare with ACTUAL behavior on C_test

The split is deterministic (sorted keys + seeded shuffle), stored in the
experiment metadata, and completely separate from the analysis code — the
estimator never touches C_test (leakage-free by construction; tests enforce
that fit inputs use the train partition only).

Reported validation metrics (Phase 6):
1. score prediction error          — MAE per-model mean train vs holdout score
2. ranking recovery                — Spearman rho / Kendall tau between the
                                     train ranking and the holdout ranking
3. pairwise decision accuracy      — fraction of pairs whose predicted winner
                                     (from train) wins on holdout
4. ranking reliability calibration — ECE / Brier / log loss / AUROC of the
                                     pairwise decision probabilities vs actual
                                     per-config outcomes on C_test
5. reliability estimation error    — MAE |p_hat_pair - actual_freq_pair|
6. CI coverage                     — fraction of pairs whose bootstrap CI of
                                     p_hat covers the observed holdout frequency

All probabilities are estimates under the *train* configuration distribution;
holdout configurations are used ONLY for evaluation, never for fitting.
"""

from __future__ import annotations

import math
import random
from statistics import mean, pstdev
from typing import Any, Sequence

from apertus_eval_prep.ranking import spearman_rank_correlation
from apertus_eval_prep.stats import kendall_tau_b

# ---------------------------------------------------------------------------
# Deterministic, leakage-free splitting
# ---------------------------------------------------------------------------


def split_config_keys(
    config_keys: Sequence[str],
    budget: int,
    *,
    seed: int = 0,
) -> dict[str, Any]:
    """Deterministic train/holdout split of configuration keys.

    ``budget`` = number of configurations available for training/observation;
    the remainder are held out. Deterministic for a given (keys, budget, seed):
    keys are sorted, then shuffled with ``random.Random(seed)``. Stores the
    full split metadata so downstream analysis can prove which partition each
    key belonged to (never recomputed from analysis results).
    """
    keys = sorted(set(config_keys))
    if budget < 1:
        raise ValueError(f"budget must be >= 1, got {budget}")
    if budget > len(keys):
        raise ValueError(
            f"budget {budget} exceeds the configuration space of {len(keys)}"
        )
    rng = random.Random(seed)
    shuffled = list(keys)
    rng.shuffle(shuffled)
    train = sorted(shuffled[:budget])
    heldout = sorted(shuffled[budget:])
    return {
        "budget": budget,
        "seed": seed,
        "n_total": len(keys),
        "n_train": len(train),
        "n_heldout": len(heldout),
        "train": train,
        "heldout": heldout,
        "method": "deterministic seeded shuffle; partition stored, not recomputed",
        "leakage_guard": "train and heldout are disjoint by construction",
    }


def partition_matrix(
    score_matrix: Sequence[Sequence[float | None]],
    split: dict[str, Any],
) -> tuple[list[list[float | None]], list[list[float | None]]]:
    """Split models x configs matrix according to a stored split.

    ``score_matrix`` columns must be ordered by sorted config keys, matching
    the split's ``train`` / ``heldout`` key lists (split_config_keys returns
    sorted lists). Returns (train, heldout).
    """
    n_c = len(score_matrix[0]) if score_matrix else 0
    if n_c != split["n_total"]:
        raise ValueError(
            f"matrix has {n_c} config columns but split expects {split['n_total']}"
        )
    lookup = {k: i for i, k in enumerate(sorted(split["train"] + split["heldout"]))}
    idx_train = [lookup[k] for k in split["train"]]
    idx_hold = [lookup[k] for k in split["heldout"]]
    train = [[row[c] for c in idx_train] for row in score_matrix]
    heldout = [[row[c] for c in idx_hold] for row in score_matrix]
    return train, heldout


# ---------------------------------------------------------------------------
# Calibration / decision metrics
# ---------------------------------------------------------------------------


def expected_calibration_error(
    probs: Sequence[float], labels: Sequence[int], *, n_bins: int = 10
) -> float | None:
    """Binned ECE: sum_b (n_b/N) * |mean(p_b) - mean(y_b)|. No points -> None."""
    pairs = [(float(p), int(y)) for p, y in zip(probs, labels) if 0.0 <= p <= 1.0]
    if not pairs:
        return None
    ece = 0.0
    for b in range(n_bins):
        b_lo = b / n_bins
        b_hi = (b + 1) / n_bins
        bin_ = [x for x in pairs if b_lo <= x[0] < b_hi or (b == n_bins - 1 and x[0] == 1.0)]
        if not bin_:
            continue
        p_bar = mean(x[0] for x in bin_)
        y_bar = mean(x[1] for x in bin_)
        ece += (len(bin_) / len(pairs)) * abs(p_bar - y_bar)
    return round(ece, 6)


def brier_score(probs: Sequence[float], labels: Sequence[int]) -> float | None:
    vals = [(float(p), int(y)) for p, y in zip(probs, labels) if 0.0 <= p <= 1.0]
    if not vals:
        return None
    return round(mean((p - y) ** 2 for p, y in vals), 6)


def log_loss(probs: Sequence[float], labels: Sequence[int], *, eps: float = 1e-12) -> float | None:
    vals = [(float(p), int(y)) for p, y in zip(probs, labels) if 0.0 <= p <= 1.0]
    if not vals:
        return None
    clipped = [(min(max(p, eps), 1.0 - eps), y) for p, y in vals]
    return round(
        mean(-(y * math.log(p) + (1 - y) * math.log(1 - p)) for p, y in clipped), 6
    )


def _average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for t in range(i, j + 1):
            ranks[order[t]] = avg
        i = j + 1
    return ranks


def auroc(probs: Sequence[float], labels: Sequence[int]) -> float | None:
    """Rank-based AUC (Mann-Whitney U) on (p, y); requires both classes."""
    pos = [float(p) for p, y in zip(probs, labels) if y == 1 and 0.0 <= p <= 1.0]
    neg = [float(p) for p, y in zip(probs, labels) if y == 0 and 0.0 <= p <= 1.0]
    if not pos or not neg:
        return None
    ranks = _average_ranks(pos + neg)
    sum_pos_ranks = sum(ranks[: len(pos)])
    n_pos = len(pos)
    n_neg = len(neg)
    auc = (sum_pos_ranks - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    return round(max(0.0, min(1.0, auc)), 6)


def coverage_fraction(
    c_los: Sequence[float | None],
    c_his: Sequence[float | None],
    targets: Sequence[float],
) -> float | None:
    pairs = [(lo, hi, t) for lo, hi, t in zip(c_los, c_his, targets)
             if lo is not None and hi is not None and t is not None]
    if not pairs:
        return None
    return round(sum(1 for lo, hi, t in pairs if lo <= t <= hi) / len(pairs), 6)
# ---------------------------------------------------------------------------
# Validation harness
# ---------------------------------------------------------------------------


def pairwise_estimates(
    train: Sequence[Sequence[float | None]],
    heldout: Sequence[Sequence[float | None]],
) -> dict[str, Any]:
    """Per-model-pair train probabilities + holdout outcomes.

    For each ordered pair (i, j):
      p_hat        = fraction of non-tied TRAIN configs where model i > model j
                     (0.5 when every train config is a tie: no decision)
      holdout_frac = same on HELDOUT configs (0.5 when all tied)
      outcomes     = per-holdout-config binary indicators for NON-TIED configs
                     only (tied configs are ambiguous and excluded from
                     calibration rather than counted as wins or losses)
      tie counts are recorded explicitly.
    Pairs with no usable train config are omitted (no imputation).
    """
    n_m = len(train)
    if n_m < 2:
        return {"pairs": []}
    usable_tr = [
        c for c in range(len(train[0]))
        if all(train[m][c] is not None for m in range(n_m))
    ]
    usable_ho = [
        c for c in range(len(heldout[0]))
        if all(heldout[m][c] is not None for m in range(n_m))
    ]
    pairs: list[dict[str, Any]] = []
    for i in range(n_m):
        for j in range(n_m):
            if i == j:
                continue
            tr_ties = sum(1 for c in usable_tr if train[i][c] == train[j][c])
            ho_ties = sum(1 for c in usable_ho if heldout[i][c] == heldout[j][c])
            tr_dec = len(usable_tr) - tr_ties
            ho_dec = len(usable_ho) - ho_ties
            if tr_dec <= 0 or ho_dec <= 0:
                continue
            p_hat = sum(1 for c in usable_tr if train[i][c] > train[j][c]) / tr_dec
            holdout_fraction = (
                sum(1 for c in usable_ho if heldout[i][c] > heldout[j][c]) / ho_dec
            )
            outcomes = [
                1.0 if heldout[i][c] > heldout[j][c] else 0.0
                for c in usable_ho if heldout[i][c] != heldout[j][c]
            ]
            pairs.append({
                "a": i, "b": j,
                "p_hat": round(p_hat, 6),
                "holdout_fraction": round(holdout_fraction, 6),
                "n_train": tr_dec,
                "n_holdout": ho_dec,
                "n_ties_train": tr_ties,
                "n_ties_holdout": ho_ties,
                "holdout_outcomes": outcomes,
            })
    return {"pairs": pairs, "n_models": n_m}


def _bootstrap_p_ci(train, a, b, *, n_boot, seed) -> tuple[float | None, float | None]:
    """Percentile CI of p_hat over config resamples (train only)."""
    import random as _random

    usable = [
        c for c in range(len(train[0]))
        if train[a][c] is not None and train[b][c] is not None
    ]
    if not usable:
        return None, None
    if n_boot < 1:
        return None, None  # bootstrap disabled -> CI unavailable, not fabricated
    rng = _random.Random(seed)
    vals = []
    for _ in range(n_boot):
        wins = 0
        for _ in range(len(usable)):
            c = rng.choice(usable)
            wins += 1 if train[a][c] > train[b][c] else 0
        vals.append(wins / len(usable))
    vals.sort()
    return vals[max(0, int(0.025 * len(vals)))], vals[min(len(vals) - 1, int(0.975 * len(vals)))]
def heldout_reliability_experiment(
    score_matrix: Sequence[Sequence[float | None]],
    config_keys: Sequence[str],
    budget: int,
    *,
    seed: int = 0,
    n_boot: int = 300,
) -> dict[str, Any]:
    """Full held-out reliability experiment for one budget.

    Deterministic given (score_matrix, config_keys, budget, seed). Splits the
    configuration columns, fits pairwise decision probabilities on train ONLY,
    and evaluates every Phase-6 metric on held-out configurations.
    """
    split = split_config_keys(config_keys, budget, seed=seed)
    train, heldout = partition_matrix(score_matrix, split)
    est = pairwise_estimates(train, heldout)

    score_errors = []
    for m in range(len(score_matrix)):
        tr = [v for v in train[m] if v is not None]
        ho = [v for v in heldout[m] if v is not None]
        if not tr or not ho:
            continue
        score_errors.append(abs(mean(tr) - mean(ho)))
    score_error = round(mean(score_errors), 6) if score_errors else None

    tr_means = [
        mean([v for v in row if v is not None]) if any(v is not None for v in row) else None
        for row in train
    ]
    ho_means = [
        mean([v for v in row if v is not None]) if any(v is not None for v in row) else None
        for row in heldout
    ]
    ranked = [(a, b) for a, b in zip(tr_means, ho_means) if a is not None and b is not None]
    spearman = kendall = None
    if len(ranked) >= 2:
        ta = [x[0] for x in ranked]
        tb = [x[1] for x in ranked]
        spearman = spearman_rank_correlation(ta, tb)
        kendall = kendall_tau_b(ta, tb)

    outcomes = [o for p in est["pairs"] for o in p["holdout_outcomes"]]
    probs_out = [p["p_hat"] for p in est["pairs"] for _ in p["holdout_outcomes"]]
    # Ties (p_hat == 0.5 or holdout fraction == 0.5) are NOT decisions and are
    # excluded from accuracy — consistent with the adaptive replay metrics.
    decidable = [p for p in est["pairs"]
                 if p["p_hat"] != 0.5 and p["holdout_fraction"] != 0.5]
    decision_acc = (
        round(sum(1 for p in decidable
                  if (p["p_hat"] > 0.5) == (p["holdout_fraction"] > 0.5)) / len(decidable), 6)
        if decidable else None
    )
    rel_err = (
        round(mean(abs(p["p_hat"] - p["holdout_fraction"]) for p in est["pairs"]), 6)
        if est["pairs"] else None
    )
    cis = [_bootstrap_p_ci(train, p["a"], p["b"], n_boot=n_boot, seed=seed)
           for p in est["pairs"]]
    c_los = [c[0] for c in cis]
    c_his = [c[1] for c in cis]
    targets = [p["holdout_fraction"] for p in est["pairs"]]

    return {
        "budget": budget,
        "seed": seed,
        "split": {k: split[k] for k in ("n_total", "n_train", "n_heldout", "method", "leakage_guard")},
        "score_prediction_error_mae": score_error,
        "ranking_recovery": {"spearman": spearman, "kendall_tau": kendall},
        "pairwise_decision_accuracy": decision_acc,
        "n_decidable_pairs": len(decidable),
        "n_pairs_excluded_ties": len(est["pairs"]) - len(decidable),
        "reliability_calibration": {
            "ece": expected_calibration_error(probs_out, outcomes),
            "brier": brier_score(probs_out, outcomes),
            "log_loss": log_loss(probs_out, outcomes),
            "auroc": auroc(probs_out, outcomes),
        },
        "reliability_estimation_error_mae": rel_err,
        "ci_coverage": coverage_fraction(c_los, c_his, targets),
        "n_pairs": len(est["pairs"]),
        "provenance": "estimator fit on train configs only; held-out configs used for evaluation",
    }


def run_heldout_experiments(
    matrix, config_keys, budgets, *, seed=0, n_boot=300
) -> dict[str, Any]:
    """Budget sweep: one held-out reliability experiment per budget."""
    return {
        "budgets": {
            b: heldout_reliability_experiment(
                matrix, config_keys, b, seed=budget_seed(seed, b), n_boot=n_boot
            )
            for b in budgets
        },
        "n_boot": n_boot,
        "base_seed": seed,
        "note": "each budget uses a deterministic derived seed (no reuse of configs)",
    }


def budget_seed(base: int, budget: int) -> int:
    """Deterministic per-budget seed so agents never share shuffle sequences."""
    return base * 10_003 + budget * 7


# ---------------------------------------------------------------------------
# Model generalization (research Phase 9): leave-one-model-out
# ---------------------------------------------------------------------------


def leave_one_model_out_experiment(
    score_matrix: Sequence[Sequence[float | None]],
    config_keys: Sequence[str],
    *,
    budget: int,
    seed: int = 0,
    n_boot: int = 0,
) -> dict[str, Any]:
    """Held-out MODEL generalization (research Phase 9B).

    Deterministically hides one model (seeded pick) and asks whether
    reliability quantities estimated from the visible models on the train
    configs describe the hidden model's behaviour — which the estimator never
    saw. Honest scope:

    - IN-distribution test: pairwise p_hat fitted on (visible x C_train),
      evaluated on (visible x C_holdout) — same quantities as
      ``heldout_reliability_experiment`` but for the visible subset.
    - OUT-of-distribution targets (reported, NOT predicted): the hidden
      model's config sensitivity (std, min/max spread over all its configs)
      and per-pair flip rates (visible vs hidden on holdout configs). These
      define the OOD generalization target; claiming to predict them from
      visible models only would require a cross-model model and is out of
      scope. Reported as association/description, explicitly labeled.

    With few models this is a low-power probe; results carry ``power`` notes.
    """
    n_m = len(score_matrix)
    if n_m < 3:
        return {"hidden_model_index": None,
                "reason": "leave-one-model-out needs >=3 models", "n_models": n_m}
    keys = sorted(set(config_keys))
    rng = random.Random(seed)
    hidden = rng.randrange(n_m)
    visible = [m for m in range(n_m) if m != hidden]

    split = split_config_keys(keys, budget, seed=seed)
    train, heldout = partition_matrix(score_matrix, split)

    # in-distribution: visible models only
    vis_train = [[train[m][c] for c in range(len(train[0]))] for m in visible]
    vis_hold = [[heldout[m][c] for c in range(len(heldout[0]))] for m in visible]
    est = pairwise_estimates(vis_train, vis_hold)
    decidable = [p for p in est["pairs"]
                 if p["p_hat"] != 0.5 and p["holdout_fraction"] != 0.5]
    vis_acc = (
        round(sum(1 for p in decidable
                  if (p["p_hat"] > 0.5) == (p["holdout_fraction"] > 0.5)) / len(decidable), 6)
        if decidable else None
    )
    vis_rel_err = (
        round(mean(abs(p["p_hat"] - p["holdout_fraction"]) for p in est["pairs"]), 6)
        if est["pairs"] else None
    )

    # OOD targets on the hidden model (never fitted)
    hidden_all = [v for v in score_matrix[hidden] if v is not None]
    hidden_hold = [v for v in heldout[hidden] if v is not None]
    hidden_stability = {
        "std_all_configs": round(pstdev(hidden_all), 6) if len(hidden_all) > 1 else None,
        "std_holdout_configs": round(pstdev(hidden_hold), 6) if len(hidden_hold) > 1 else None,
        "spread_all_configs": (
            round(max(hidden_all) - min(hidden_all), 6) if hidden_all else None),
        "n_holdout_configs": len(hidden_hold),
    }
    flip_rates: list[dict[str, Any]] = []
    for m in visible:
        ho_pairs = [(heldout[hidden][c], heldout[m][c])
                    for c in range(len(heldout[0]))
                    if heldout[hidden][c] is not None and heldout[m][c] is not None]
        flips = sum(1 for h, v in ho_pairs if h == v)
        wins = sum(1 for h, v in ho_pairs if h > v)
        if ho_pairs:
            flip_rates.append({
                "visible_model_index": m,
                "hidden_wins_fraction": round(wins / len(ho_pairs), 6),
                "tie_fraction": round(flips / len(ho_pairs), 6),
                "n_configs": len(ho_pairs),
            })
    return {
        "experiment_type": "leave_one_model_out",
        "budget": budget,
        "seed": seed,
        "hidden_model_index": hidden,
        "n_visible_models": len(visible),
        "split": {k: split[k] for k in ("n_total", "n_train", "n_heldout", "method")},
        "in_distribution_visible": {
            "pairwise_decision_accuracy": vis_acc,
            "reliability_estimation_error_mae": vis_rel_err,
            "n_decidable_pairs": len(decidable),
        },
        "out_of_distribution_hidden": {
            "stability": hidden_stability,
            "pair_flip_rates": flip_rates,
            "label": "OOD targets reported, not predicted (no cross-model estimator fitted)",
        },
        "power_note": "low-power probe with few models; descriptive only",
        "provenance": "hidden model excluded from all fitting",
    }


def leave_one_model_out_sweep(
    score_matrix, config_keys, *, budgets, seed=0
) -> dict[str, Any]:
    """One leave-one-model-out experiment per budget (deterministic seeds)."""
    return {
        "budgets": {
            b: leave_one_model_out_experiment(
                score_matrix, config_keys, budget=b, seed=budget_seed(seed, b)
            )
            for b in budgets
        },
        "base_seed": seed,
        "note": "each budget uses a deterministic derived seed",
    }
