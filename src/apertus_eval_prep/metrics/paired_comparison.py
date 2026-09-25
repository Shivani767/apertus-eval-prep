"""Paired baseline/candidate comparisons with explicit missing-data accounting."""
from __future__ import annotations

import math
import random
from typing import Any, Mapping, Sequence

from apertus_eval_prep.metrics.confidence_intervals import _percentile_indices
from apertus_eval_prep.metrics.regression import RegressionStatus, classify_regression


def _as_map(
    values: Sequence[Any] | Mapping[str, Any], ids: Sequence[str] | None = None
) -> tuple[dict[str, float], int]:
    """Coerce observations while skipping missing, invalid, and non-finite values."""
    invalid = 0
    out: dict[str, float] = {}
    if isinstance(values, Mapping):
        pairs = values.items()
    else:
        if ids is None:
            ids = [str(i) for i in range(len(values))]
        if len(ids) != len(values):
            raise ValueError("ids must have the same length as values")
        pairs = zip(ids, values)
    for key, value in pairs:
        if value is None:
            invalid += 1
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            invalid += 1
            continue
        if math.isfinite(number):
            out[str(key)] = number
        else:
            invalid += 1
    return out, invalid


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def paired_comparison(
    baseline: Sequence[Any] | Mapping[str, Any],
    candidate: Sequence[Any] | Mapping[str, Any],
    *,
    baseline_ids: Sequence[str] | None = None,
    candidate_ids: Sequence[str] | None = None,
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 0,
    practical_effect_threshold: float = 0.02,
    min_sample_size: int = 20,
    safety_critical: bool = False,
) -> dict[str, Any]:
    """Compare aligned observations and return effect, CI, and status.

    ``candidate - baseline`` is the delta convention.  Missing or failed examples
    are excluded only when they are absent from both aligned series; the number
    dropped is always reported.
    """
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be in [0, 1]")
    left, left_invalid = _as_map(baseline, baseline_ids)
    right, right_invalid = _as_map(candidate, candidate_ids)
    shared = sorted(set(left).intersection(right))
    deltas = [right[key] - left[key] for key in shared]
    n = len(deltas)
    if not deltas:
        return {
            "baseline_mean": None, "candidate_mean": None, "delta": None,
            "ci_low": None, "ci_high": None, "effect_size": None,
            "effect_size_name": "paired_cohen_dz", "effect_size_valid": False,
            "n_paired": 0, "n_dropped": len(set(left) ^ set(right)) + left_invalid + right_invalid,
            "n_invalid_baseline": left_invalid, "n_invalid_candidate": right_invalid,
            "status": RegressionStatus.INCONCLUSIVE.value,
            "method": "paired_bootstrap", "limitations": ["no aligned finite observations"],
        }
    rng = random.Random(seed)
    boot = []
    for _ in range(max(1, n_boot)):
        sample = [deltas[rng.randrange(n)] for _ in range(n)]
        boot.append(_mean(sample))
    boot.sort()
    lo_i, hi_i = _percentile_indices(len(boot), alpha)
    lo, hi = boot[lo_i], boot[hi_i]
    baseline_mean = _mean([left[k] for k in shared])
    candidate_mean = _mean([right[k] for k in shared])
    sd = math.sqrt(sum((d - _mean(deltas)) ** 2 for d in deltas) / n) if n else 0.0
    effect_valid = n >= 2 and sd > 0.0
    effect = _mean(deltas) / sd if effect_valid else None
    status = classify_regression(
        _mean(deltas), (lo, hi), n=n, practical_effect_threshold=practical_effect_threshold,
        min_sample_size=min_sample_size, safety_critical=safety_critical,
    )
    return {
        "baseline_mean": baseline_mean, "candidate_mean": candidate_mean,
        "delta": _mean(deltas), "ci_low": lo, "ci_high": hi, "effect_size": effect,
        "effect_size_name": "paired_cohen_dz", "effect_size_valid": effect_valid,
        "n_paired": n, "n_dropped": len(set(left) ^ set(right)) + left_invalid + right_invalid,
        "n_invalid_baseline": left_invalid, "n_invalid_candidate": right_invalid,
        "n_boot": max(1, n_boot),
        "seed": seed, "method": "paired_bootstrap", "status": status.value,
        "limitations": ["CI is bootstrap uncertainty, not a proof of practical importance"],
    }


def paired_effect_size(baseline: Sequence[float], candidate: Sequence[float]) -> float | None:
    """Return paired Cohen's dz, or ``None`` when it is not defined."""
    if len(baseline) != len(candidate) or len(baseline) < 2:
        return None
    diffs: list[float] = []
    for left, right in zip(baseline, candidate):
        try:
            delta = float(right) - float(left)
        except (TypeError, ValueError):
            continue
        if math.isfinite(delta):
            diffs.append(delta)
    if len(diffs) < 2:
        return None
    mean = _mean(diffs)
    sd = math.sqrt(sum((d - mean) ** 2 for d in diffs) / len(diffs))
    return mean / sd if sd > 0.0 else None


__all__ = ["paired_comparison", "paired_effect_size"]
