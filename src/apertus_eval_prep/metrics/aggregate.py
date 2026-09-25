"""Small, dependency-free aggregate metric helpers."""
from __future__ import annotations

import math
from statistics import mean, median, pstdev
from typing import Any, Iterable, Mapping, Sequence


def _finite(values: Iterable[Any]) -> list[float]:
    out: list[float] = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            out.append(number)
    return out


def percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be between 0 and 1")
    ordered = sorted(float(v) for v in values)
    index = (len(ordered) - 1) * q
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def summarize_scores(
    scores: Iterable[Any], *, total: int | None = None,
    failed: int = 0, evidence_class: str = "MEASURED",
) -> dict[str, Any]:
    """Summarize scores while retaining coverage and failure counts."""
    values = _finite(scores)
    n = len(values)
    denominator = total if total is not None else n
    if n == 0:
        return {
            "count": 0, "n_total": denominator, "n_scored": 0, "n_failed": failed,
            "mean": None, "median": None, "std": None, "variance": None, "standard_error": None,
            "min": None, "max": None, "p25": None, "p75": None, "p95": None,
            "accuracy": None, "evidence_class": evidence_class,
            "missing_or_invalid": max(0, denominator - n - failed),
        }
    avg = mean(values)
    sd = pstdev(values) if n > 1 else 0.0
    return {
        "count": n, "n_total": denominator, "n_scored": n, "n_failed": failed,
        "mean": avg, "median": median(values), "std": sd, "variance": sd * sd,
        "standard_error": sd / math.sqrt(n) if n else None,
        "min": min(values), "max": max(values),
        "p25": percentile(values, 0.25), "p75": percentile(values, 0.75),
        "p95": percentile(values, 0.95), "accuracy": avg,
        "evidence_class": evidence_class,
        "missing_or_invalid": max(0, denominator - n - failed),
    }


def summarize_latencies(latencies: Iterable[Any]) -> dict[str, Any]:
    values = _finite(latencies)
    summary = summarize_scores(values, total=len(values))
    summary["mean_ms"] = summary["mean"]
    summary["p50_ms"] = percentile(values, 0.50)
    summary["p95_ms"] = percentile(values, 0.95)
    return summary


def summarize_by(rows: Iterable[Mapping[str, Any]], key: str, value_key: str = "score") -> dict[str, Any]:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        value = row.get(value_key)
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        grouped.setdefault(str(row.get(key, "unknown")), []).append(number)
    return {name: summarize_scores(values) for name, values in sorted(grouped.items())}


__all__ = ["percentile", "summarize_scores", "summarize_latencies", "summarize_by"]
