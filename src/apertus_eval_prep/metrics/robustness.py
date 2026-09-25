"""Robustness and condition-sensitivity summaries for variance studies."""
from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean, pvariance
from typing import Any, Iterable, Mapping, Sequence

from apertus_eval_prep.metrics.aggregate import summarize_scores
from apertus_eval_prep.metrics.confidence_intervals import bootstrap_mean_ci


def robust_capability_score(
    scores: Sequence[float], *, lambda_: float = 1.0,
) -> dict[str, Any]:
    """Compute the project-defined experimental Robust Capability Score.

    ``RCS = mean_quality - lambda * configuration_variance``.  It is explicitly
    not a universal benchmark metric and should be interpreted alongside its
    components and sample count.
    """
    try:
        lambda_value = float(lambda_)
    except (TypeError, ValueError) as exc:
        raise ValueError("lambda_ must be a finite non-negative number") from exc
    if not math.isfinite(lambda_value) or lambda_value < 0:
        raise ValueError("lambda_ must be a finite non-negative number")
    values: list[float] = []
    for value in scores:
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            values.append(number)
    if not values:
        return {"score": None, "mean_quality": None, "configuration_variance": None,
                "lambda": lambda_value, "n": 0, "n_conditions": 0, "experimental": True,
                "formula": "RCS = mean_quality - lambda * configuration_variance",
                "limitations": ["no scored observations"]}
    avg = mean(values)
    variance = pvariance(values)
    return {"score": avg - lambda_value * variance, "mean_quality": avg,
            "configuration_variance": variance, "lambda": lambda_value,
            "n": len(values), "n_conditions": len(values), "experimental": True,
            "formula": "RCS = mean_quality - lambda * configuration_variance",
            "limitations": ["project-defined experimental score; not a standard universal metric"]}


def _score_value(row: Mapping[str, Any]) -> float | None:
    try:
        value = float(row.get("score"))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _outcome(row: Mapping[str, Any]) -> bool:
    if row.get("correct") is not None:
        return bool(row.get("correct"))
    value = _score_value(row)
    return value is not None and value >= 0.5


def factor_summary(
    rows: Iterable[Mapping[str, Any]], factor: str, *, n_boot: int = 400, seed: int = 0
) -> dict[str, Any]:
    groups: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        value = _score_value(row)
        if value is not None:
            groups[str(row.get(factor, "unknown"))].append(value)
    levels: dict[str, dict[str, Any]] = {}
    for key, values in sorted(groups.items()):
        summary = summarize_scores(values)
        summary["confidence_interval"] = bootstrap_mean_ci(values, n_boot=n_boot, seed=seed)
        levels[key] = summary
    return {
        "factor": factor,
        "levels": levels,
        "n": sum(len(values) for values in groups.values()),
    }


_PROMPT_FACTORS = {"prompt_id", "prompt_template", "prompt_version", "template"}
_BACKEND_FACTORS = {"backend"}
_QUANTIZATION_FACTORS = {"quantization"}


def _sensitive_labels(
    observations: list[Mapping[str, Any]], factors: Sequence[str]
) -> list[str]:
    labels: list[str] = []
    groups = (
        ("prompt_sensitive_failure", _PROMPT_FACTORS),
        ("backend_sensitive_failure", _BACKEND_FACTORS),
        ("quantization_sensitive_failure", _QUANTIZATION_FACTORS),
    )
    for label, aliases in groups:
        for factor in factors:
            if factor not in aliases:
                continue
            levels: dict[str, list[bool]] = defaultdict(list)
            for observation in observations:
                if _score_value(observation) is not None:
                    levels[str(observation.get(factor, "unknown"))].append(_outcome(observation))
            means = [sum(values) / len(values) for values in levels.values() if values]
            if len(means) > 1 and max(means) != min(means) and any(
                not outcome for values in levels.values() for outcome in values
            ):
                labels.append(label)
                break
    return labels


def analyze_condition_sensitivity(
    rows: Iterable[Mapping[str, Any]], factors: Sequence[str], *, n_boot: int = 400, seed: int = 0
) -> dict[str, Any]:
    """Rank factor instability and classify stable/sensitive example outcomes."""
    materialized = [dict(row) for row in rows]
    factor_rows = [
        factor_summary(materialized, factor, n_boot=n_boot, seed=seed) for factor in factors
    ]
    ranked: list[dict[str, Any]] = []
    for item in factor_rows:
        levels = item["levels"]
        means = [v["mean"] for v in levels.values() if v["mean"] is not None]
        spread = max(means) - min(means) if means else None
        ranked.append({
            **item,
            "mean_spread": spread,
            "unstable": bool(spread is not None and spread > 0.0),
        })
    ranked.sort(key=lambda item: (item["mean_spread"] is not None, item["mean_spread"] or -1), reverse=True)
    by_example: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in materialized:
        if _score_value(row) is not None:
            by_example[str(row.get("example_id", "unknown"))].append(row)
    sensitive: list[dict[str, Any]] = []
    stable_success_ids: list[str] = []
    stable_failure_ids: list[str] = []
    for example_id, observations in sorted(by_example.items()):
        outcomes = [_outcome(obs) for obs in observations]
        if all(outcomes):
            stable_success_ids.append(example_id)
            continue
        if not any(outcomes):
            stable_failure_ids.append(example_id)
            continue
        labels = _sensitive_labels(observations, factors)
        sensitive.append({
            "example_id": example_id,
            "n_conditions": len(outcomes),
            "success_count": sum(outcomes),
            "classification": labels[0] if labels else "condition_sensitive",
            "classifications": labels or ["condition_sensitive"],
        })
    return {
        "factors": ranked,
        "most_unstable_factor": ranked[0]["factor"] if ranked else None,
        "unstable_conditions": [item["factor"] for item in ranked if item["unstable"]],
        "stable_success": len(stable_success_ids),
        "stable_failure": len(stable_failure_ids),
        "stable_success_examples": stable_success_ids,
        "stable_failure_examples": stable_failure_ids,
        "condition_sensitive": sensitive,
        "sensitive_failures": sensitive,
        "representative_sensitive_failures": sensitive[:10],
    }


__all__ = ["robust_capability_score", "factor_summary", "analyze_condition_sensitivity"]
