"""Deterministic bootstrap intervals for bounded and continuous scores."""
from __future__ import annotations

import math
import random
from typing import Sequence

from apertus_eval_prep.stats import wilson_interval


def _percentile_indices(n_boot: int, alpha: float) -> tuple[int, int]:
    """Return valid percentile indices, including the alpha=1 boundary."""
    if alpha <= 0.0:
        return 0, n_boot - 1
    if alpha >= 1.0:
        return 0, n_boot - 1
    lo = max(0, min(n_boot - 1, int(math.floor((alpha / 2.0) * n_boot))))
    hi = max(0, min(n_boot - 1, int(math.ceil((1.0 - alpha / 2.0) * n_boot)) - 1))
    return lo, hi


def bootstrap_mean_ci(
    values: Sequence[float], *, n_boot: int = 400, alpha: float = 0.05, seed: int = 0,
) -> dict[str, float | int | None]:
    """Percentile bootstrap CI for a mean, with explicit small-sample metadata."""
    clean: list[float] = []
    for value in values:
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            clean.append(number)
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be in [0, 1]")
    if not clean or n_boot < 1:
        return {"lo": None, "hi": None, "mean": None, "n": len(clean), "n_boot": n_boot, "method": "bootstrap_percentile"}
    rng = random.Random(seed)
    n = len(clean)
    means = []
    for _ in range(n_boot):
        means.append(sum(clean[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    lo_i, hi_i = _percentile_indices(n_boot, alpha)
    return {
        "lo": means[lo_i], "hi": means[hi_i], "mean": sum(clean) / n,
        "n": n, "n_boot": n_boot, "seed": seed, "method": "bootstrap_percentile",
        "alpha": alpha,
    }


def bootstrap_correctness_ci(correct: Sequence[bool], *, n_boot: int = 400, alpha: float = 0.05, seed: int = 0) -> dict:
    values = [1.0 if bool(v) else 0.0 for v in correct]
    result = bootstrap_mean_ci(values, n_boot=n_boot, alpha=alpha, seed=seed)
    if correct:
        result["wilson"] = {"lo": wilson_interval(sum(bool(v) for v in correct), len(correct))[0],
                            "hi": wilson_interval(sum(bool(v) for v in correct), len(correct))[1]}
    return result


__all__ = ["bootstrap_mean_ci", "bootstrap_correctness_ci"]
