"""Ranking robustness layer (Phase 3). Reuses stats.rank_high_is_better.

All inputs are already-measured score vectors — no runs are invented.
Spearman: Pearson correlation of competition ranks (average-tie), None when a
rank vector has zero variance. Win-rates / rank distributions / P(#1) are
empirical frequencies over the given configs. Bootstrap rank stability resamples
configs (not items) with a fixed seed for reproducibility.
"""

from __future__ import annotations

import math
import random
import statistics
from typing import Sequence

from apertus_eval_prep.stats import kendall_tau_b, rank_high_is_better


def spearman_rank_correlation(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Spearman rho via Pearson correlation of competition ranks. None if degenerate."""
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    rx = rank_high_is_better(list(xs))
    ry = rank_high_is_better(list(ys))
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return (num / den) if den else None


def pairwise_win_rates(score_matrix: Sequence[Sequence[float]]) -> list[list[float | None]]:
    """Fraction of configs where row model strictly beats column model.

    score_matrix[m][c] = accuracy of model m under config c. Missing (None)
    configs are skipped pairwise; diagonal is None. Ties are not wins.
    """
    n_m = len(score_matrix)
    out: list[list[float | None]] = [[None] * n_m for _ in range(n_m)]
    for i in range(n_m):
        for j in range(n_m):
            if i == j:
                continue
            wins = tot = 0
            for a, b in zip(score_matrix[i], score_matrix[j]):
                if a is None or b is None:
                    continue
                tot += 1
                if a > b:
                    wins += 1
            out[i][j] = (wins / tot) if tot else None
    return out


def rank_distributions(score_matrix: Sequence[Sequence[float]]) -> list[dict[str, float | int]]:
    """Per-model rank histogram over configs: mean/var rank, P(#1), n configs.

    Ranks use competition ranking (1 = best); configs with any missing score for
    the model set are skipped and counted in `n_skipped`.
    """
    n_m = len(score_matrix)
    n_c = len(score_matrix[0]) if n_m else 0
    dists = []
    skipped = 0
    cols: list[list[float]] = []
    for c in range(n_c):
        col = [score_matrix[m][c] for m in range(n_m)]
        if any(v is None for v in col):
            skipped += 1
            continue
        cols.append(rank_high_is_better(col))
    for m in range(n_m):
        ranks = [cols[c][m] for c in range(len(cols))]
        dists.append(
            {
                "mean_rank": statistics.mean(ranks) if ranks else None,
                "rank_variance": statistics.pvariance(ranks) if len(ranks) > 1 else 0.0,
                "p_rank_1": sum(1 for r in ranks if r == 1.0) / len(ranks) if ranks else None,
                "rank_min": min(ranks) if ranks else None,
                "rank_max": max(ranks) if ranks else None,
                "n_configs": len(ranks),
                "n_skipped": skipped,
            }
        )
    return dists


def bootstrap_ranking_stability(
    score_matrix: Sequence[Sequence[float]],
    *,
    n_boot: int = 1000,
    seed: int = 0,
) -> dict[str, float | int | None]:
    """Resample configs with replacement; report mean Kendall-tau vs full ranking.

    Reference ranking = competition ranks on per-model mean accuracy.
    Each bootstrap replicate ranks models on resampled-config means and compares
    with Kendall tau-b. Returns mean tau, fraction of replicates with a pairwise
    reversal vs reference, n models/configs. Deterministic given seed.
    """
    from apertus_eval_prep.stats import pairwise_reversals

    n_m = len(score_matrix)
    full = [r for r in zip(*score_matrix)]
    usable = [c for c in full if all(v is not None for v in c)]
    if n_m < 2 or not usable:
        return {"mean_tau": None, "p_any_reversal": None,
                "n_models": n_m, "n_configs": len(usable)}
    ref_acc = [statistics.mean(score_matrix[m][c] for c in range(len(usable))) for m in range(n_m)]
    ref_ranks = rank_high_is_better(ref_acc)
    rng = random.Random(seed)
    taus: list[float] = []
    reversals = 0
    for _ in range(n_boot):
        sample = [rng.choice(usable) for _ in usable]
        acc = [statistics.mean(col[m] for col in sample) for m in range(n_m)]
        ranks = rank_high_is_better(acc)
        tau = kendall_tau_b(ref_ranks, ranks)
        taus.append(1.0 if tau is None else tau)
        if pairwise_reversals(ref_ranks, ranks) > 0:
            reversals += 1
    return {"mean_tau": statistics.mean(taus), "p_any_reversal": reversals / n_boot,
            "n_models": n_m, "n_configs": len(usable)}
