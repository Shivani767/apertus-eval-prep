"""Evaluation Sensitivity Index (ESI): how much does one factor move a score?

Deliberately separate from the existing ERS. ERS aggregates several reliability
components into one provisional number; ESI answers a narrower and more
auditable question -- *for a single factor, how large is the movement it
produces, relative to an explicitly declared uncertainty scale?*

Everything is reported before anything is combined:

* ``absolute_delta`` -- spread of level means, in the score's own units;
* ``relative_delta`` -- that spread over the declared baseline level mean;
* ``standardized_effect`` -- Cohen's h, the effect size for a proportion;
* ``confidence_interval`` -- seeded bootstrap interval on the spread;
* ``esi`` -- the derived diagnostic, and only when a scale is declared.

ESI is ``absolute_delta / uncertainty_scale``: how many declared uncertainty
units the factor's effect spans. It is a *diagnostic*, not a quality score, and
a composite over factors is deliberately not produced. The formula and every
assumption are in ``definitions`` in the artifact itself. When no uncertainty
scale is declared, ``esi`` is ``null`` with a reason rather than a number
invented from a convenient default.
"""

from __future__ import annotations

import random
import statistics
from typing import Any, Mapping, Sequence

from apertus_eval_prep.core.evidence import normalize_evidence
from apertus_eval_prep.stability import cohens_h
from apertus_eval_prep.stats import wilson_interval

SENSITIVITY_SCHEMA_VERSION = "1.0"

SENSITIVITY_DISCLAIMER = (
    "Evaluation sensitivity describes how far a measured score moves across the "
    "levels of one factor, on the evaluated configurations. It is a diagnostic "
    "and is not a model quality score, a causal claim, or production approval."
)


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _level_means(
    rows: Sequence[Mapping[str, Any]], factor: str, score_key: str
) -> dict[str, list[float]]:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        value = _number(row.get(score_key))
        if value is None or factor not in row:
            continue
        grouped.setdefault(str(row[factor]), []).append(value)
    return grouped


def _bootstrap_spread(
    values: Sequence[Sequence[float]], *, n_boot: int, seed: int
) -> list[float] | None:
    """Percentile bootstrap on (max level mean - min level mean)."""
    if n_boot <= 0 or len(values) < 2 or any(len(v) < 2 for v in values):
        return None
    rng = random.Random(seed)
    spreads: list[float] = []
    for _ in range(n_boot):
        resampled = [statistics.mean(rng.choices(group, k=len(group))) for group in values]
        spreads.append(max(resampled) - min(resampled))
    spreads.sort()
    low = spreads[int(0.025 * (n_boot - 1))]
    high = spreads[int(0.975 * (n_boot - 1))]
    return [round(low, 6), round(high, 6)]


def wilson_uncertainty_scale(accuracy: float, n: int) -> float | None:
    """A defensible ESI unit: the Wilson 95% half-width at a declared n."""
    low, high = wilson_interval(round(float(accuracy) * n), int(n))
    if low is None or high is None:
        return None
    return round((high - low) / 2.0, 6)



def factor_sensitivity_index(
    rows: Sequence[Mapping[str, Any]],
    factors: Sequence[str],
    *,
    score_key: str = "score",
    baseline_level: str | None = None,
    uncertainty_scale: float | None = None,
    n_boot: int = 500,
    seed: int = 0,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Report per-factor sensitivity, with ESI only when a scale is declared.

    ``rows`` are already-scored observations carrying the factor columns and a
    numeric score. ``uncertainty_scale`` is the declared unit ESI is measured
    in -- typically a Wilson half-width at a declared sample size, or a minimum
    effect of interest. Without it the absolute and relative deltas and the
    effect size are still reported, and ``esi`` is ``null`` with a reason.
    """
    materialised = [dict(row) for row in rows]
    scale = _number(uncertainty_scale)
    results: list[dict[str, Any]] = []

    for factor in factors:
        grouped = _level_means(materialised, factor, score_key)
        if not grouped:
            results.append({
                "factor": factor,
                "status": "UNAVAILABLE",
                "reason": f"no scored observation carries the factor {factor!r}",
                "n_levels": 0,
                "absolute_delta": None,
                "relative_delta": None,
                "standardized_effect_cohens_h": None,
                "confidence_interval_95": None,
                "esi": None,
            })
            continue
        level_means = {level: statistics.mean(values) for level, values in grouped.items()}
        lowest = min(level_means, key=lambda k: level_means[k])
        highest = max(level_means, key=lambda k: level_means[k])
        spread = round(level_means[highest] - level_means[lowest], 6)
        base_level = baseline_level if baseline_level in level_means else lowest
        base_mean = level_means[base_level]
        entry: dict[str, Any] = {
            "factor": factor,
            "status": "MEASURED",
            "n_levels": len(grouped),
            "n_observations": sum(len(v) for v in grouped.values()),
            "level_means": {k: round(v, 6) for k, v in sorted(level_means.items())},
            "baseline_level": base_level,
            "min_level": lowest,
            "max_level": highest,
            "absolute_delta": spread,
            "relative_delta": round(spread / abs(base_mean), 6) if base_mean else None,
            "standardized_effect_cohens_h": (
                round(cohens_h(level_means[lowest], level_means[highest]), 6)
                if 0.0 <= level_means[lowest] <= 1.0 and 0.0 <= level_means[highest] <= 1.0
                else None
            ),
            "confidence_interval_95": _bootstrap_spread(
                list(grouped.values()), n_boot=n_boot, seed=seed
            ),
        }
        if scale and scale > 0:
            entry["esi"] = round(spread / scale, 6)
            entry["esi_scale"] = scale
        else:
            entry["esi"] = None
            entry["esi_scale"] = None
            entry["esi_reason"] = (
                "no uncertainty scale was declared; ESI is dimensionless by "
                "definition and is not computed from an assumed default"
            )
        results.append(entry)


    measured = [r for r in results if r["status"] == "MEASURED"]
    ranked = sorted(measured, key=lambda r: r["absolute_delta"] or 0.0, reverse=True)
    return {
        "metric": "evaluation_sensitivity",
        "schema_version": SENSITIVITY_SCHEMA_VERSION,
        "status": "ok" if measured else "insufficient_design",
        "n_factors": len(factors),
        "n_factors_measured": len(measured),
        "uncertainty_scale": scale,
        "n_boot": n_boot,
        "seed": seed,
        "factors": results,
        "most_sensitive_factor": ranked[0]["factor"] if ranked else None,
        "least_sensitive_factor": ranked[-1]["factor"] if len(ranked) > 1 else None,
        "definitions": {
            "absolute_delta": "max level mean - min level mean, in score units",
            "relative_delta": "absolute_delta / |baseline level mean|",
            "standardized_effect_cohens_h": "Cohen's h between the extreme level "
                                            "means; defined for proportions in [0, 1]",
            "confidence_interval_95": "seeded bootstrap percentile interval on the spread",
            "esi": "absolute_delta / declared uncertainty scale; dimensionless",
        },
        "assumptions": [
            "Level means are compared directly, so a factor is assessed over its "
            "full observed range rather than pairwise.",
            "Cohen's h is used because the score is a proportion; a bounded "
            "continuous metric would need a different standardised effect.",
            "ESI depends entirely on the declared scale, which is data supplied "
            "by the caller, not a convention baked into the code.",
        ],
        "limits": [
            "Sensitivity is measured over the evaluated levels only and does not "
            "extrapolate to unevaluated ones.",
            "ESI is a diagnostic for comparing factors against a declared scale; "
            "it is not a quality score and no composite over factors is produced.",
            "A factor with a single observed level has no spread and is not ranked.",
        ],
        "disclaimer": SENSITIVITY_DISCLAIMER,
        "evidence": normalize_evidence(evidence),
    }


__all__ = [
    "SENSITIVITY_DISCLAIMER",
    "SENSITIVITY_SCHEMA_VERSION",
    "factor_sensitivity_index",
    "wilson_uncertainty_scale",
]

