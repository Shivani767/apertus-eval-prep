"""Configurable regression classification for release decisions."""
from __future__ import annotations

from enum import StrEnum
from typing import Any


class RegressionStatus(StrEnum):
    CONFIRMED_REGRESSION = "CONFIRMED_REGRESSION"
    LIKELY_REGRESSION = "LIKELY_REGRESSION"
    NO_MEANINGFUL_CHANGE = "NO_MEANINGFUL_CHANGE"
    LIKELY_IMPROVEMENT = "LIKELY_IMPROVEMENT"
    CONFIRMED_IMPROVEMENT = "CONFIRMED_IMPROVEMENT"
    INCONCLUSIVE = "INCONCLUSIVE"


def classify_regression(
    delta: float | None,
    confidence_interval: tuple[float | None, float | None] | list[float | None],
    *,
    n: int,
    practical_effect_threshold: float = 0.02,
    min_sample_size: int = 20,
    safety_critical: bool = False,
) -> RegressionStatus:
    """Classify a candidate-minus-baseline delta without hidden thresholds.

    The practical threshold defines meaningful change.  A confidence interval
    wholly beyond zero provides stronger evidence than a point estimate; small
    samples remain inconclusive.  Safety-critical mode escalates a meaningful
    negative point estimate but never turns missing evidence into a pass.
    """
    if delta is None or n < min_sample_size or practical_effect_threshold < 0:
        return RegressionStatus.INCONCLUSIVE
    lo, hi = confidence_interval
    if lo is None or hi is None:
        return RegressionStatus.INCONCLUSIVE
    threshold = float(practical_effect_threshold)
    if hi < -threshold:
        return RegressionStatus.CONFIRMED_REGRESSION
    if lo > threshold:
        return RegressionStatus.CONFIRMED_IMPROVEMENT
    if delta < -threshold and (hi < 0 or safety_critical):
        return RegressionStatus.LIKELY_REGRESSION
    if delta > threshold and lo > 0:
        return RegressionStatus.LIKELY_IMPROVEMENT
    if -threshold <= delta <= threshold and lo >= -threshold and hi <= threshold:
        return RegressionStatus.NO_MEANINGFUL_CHANGE
    return RegressionStatus.INCONCLUSIVE


def regression_report(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Convenience wrapper returning a serializable classification report."""
    status = classify_regression(*args, **kwargs)
    return {"status": status.value, "status_enum": status.name}


__all__ = ["RegressionStatus", "classify_regression", "regression_report"]
