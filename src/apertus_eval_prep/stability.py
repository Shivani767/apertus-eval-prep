"""Evaluation stability metrics (Phase 2).

All functions operate on already-measured score lists or paired correctness
vectors — they never invent runs. Definitions:

- variance/population-std: spread of scores across configs (descriptive).
- range: max - min (sensitive to outliers; report with std, never alone).
- coef_of_variation: std/mean; None when mean is 0 (division undefined).
- bootstrap_ci: percentile CI of the mean under resampling (seeded, reproducible).
- paired_difference: per-item B - A on matched ids (missing ids dropped, counted).
- cohens_h: 2*asin(sqrt(p1)) - 2*asin(sqrt(p2)) for two proportions.
- *_sensitivity: max pairwise |delta| within a factor group (OFAT-safe).
"""

from __future__ import annotations

import math
import random
from statistics import mean, pstdev, stdev
from typing import Any, Sequence


def score_variance(scores: Sequence[float]) -> float | None:
    vals = [float(s) for s in scores if s is not None]
    if len(vals) < 2:
        return None
    return pstdev(vals) ** 2


def score_std(scores: Sequence[float], *, sample: bool = False) -> float | None:
    vals = [float(s) for s in scores if s is not None]
    if len(vals) < 2:
        return None
    return (stdev if sample else pstdev)(vals)


def score_range(scores: Sequence[float]) -> float | None:
    vals = [float(s) for s in scores if s is not None]
    if len(vals) < 2:
        return None
    return max(vals) - min(vals)


def coef_of_variation(scores: Sequence[float]) -> float | None:
    vals = [float(s) for s in scores if s is not None]
    if len(vals) < 2:
        return None
    mu = mean(vals)
    if mu == 0:
        return None
    return pstdev(vals) / abs(mu)


def bootstrap_ci_mean(
    scores: Sequence[float],
    *,
    n_boot: int = 2000,
    ci: float = 0.95,
    seed: int = 0,
) -> dict[str, Any]:
    """Percentile bootstrap CI of the mean. Seeded; empty/degenerate -> None band."""
    vals = [float(s) for s in scores if s is not None]
    if not vals or n_boot < 100:
        return {"mean": mean(vals) if vals else None, "lo": None, "hi": None,
                "n": len(vals), "n_boot": n_boot, "seed": seed}
    rng = random.Random(seed)
    n = len(vals)
    boot = [mean(rng.choice(vals) for _ in range(n)) for _ in range(n_boot)]
    boot.sort()
    alpha = 1.0 - ci
    lo_i = max(0, int((alpha / 2) * n_boot))
    hi_i = min(n_boot - 1, int((1 - alpha / 2) * n_boot))
    return {"mean": mean(vals), "lo": boot[lo_i], "hi": boot[hi_i],
            "n": n, "n_boot": n_boot, "seed": seed}


def paired_difference(
    a_by_id: dict[str, bool], b_by_id: dict[str, bool]
) -> dict[str, Any]:
    """Per-item correctness difference B - A on shared ids.

    Returns delta_mean (fraction of items B gains over A), n_paired,
    n_dropped (ids not shared — reported, never silently filled).
    """
    shared = sorted(set(a_by_id) & set(b_by_id))
    dropped = len(set(a_by_id) ^ set(b_by_id) - set(shared)) + (
        len(set(a_by_id) | set(b_by_id)) - len(shared) - len(set(a_by_id) ^ set(b_by_id))
    )
    # Simpler exact count of unshared ids:
    dropped = len((set(a_by_id) | set(b_by_id)) - set(shared))
    if not shared:
        return {"delta_mean": None, "n_paired": 0, "n_dropped": dropped}
    delta = mean((1 if b_by_id[i] else 0) - (1 if a_by_id[i] else 0) for i in shared)
    return {"delta_mean": delta, "n_paired": len(shared), "n_dropped": dropped}


def cohens_h(p1: float, p2: float) -> float | None:
    """Cohen's h effect size between two proportions in [0, 1]."""
    if not (0.0 <= p1 <= 1.0 and 0.0 <= p2 <= 1.0):
        return None
    return 2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p2))


def factor_sensitivity(grouped: dict[str, list[float]]) -> dict[str, Any]:
    """Max pairwise |mean_a - mean_b| across factor levels (OFAT-safe summary).

    Input maps level -> list of scores (already measured). Levels with no scores
    are reported in `empty_levels`, never imputed.
    """
    means = {k: (mean(v) if v else None) for k, v in grouped.items()}
    empty = sorted(k for k, m in means.items() if m is None)
    present = [(k, m) for k, m in means.items() if m is not None]
    if len(present) < 2:
        return {"max_abs_delta": None, "pair": None, "means": means,
                "empty_levels": empty}
    best: tuple[str, str] | None = None
    best_d = -1.0
    for i in range(len(present)):
        for j in range(i + 1, len(present)):
            d = abs(present[i][1] - present[j][1])
            if d > best_d:
                best_d, best = d, (present[i][0], present[j][0])
    return {"max_abs_delta": best_d, "pair": best, "means": means,
            "empty_levels": empty}
