"""Statistical and decision metrics."""
from .aggregate import percentile, summarize_by, summarize_latencies, summarize_scores
from .confidence_intervals import bootstrap_correctness_ci, bootstrap_mean_ci
from .paired_comparison import paired_comparison, paired_effect_size
from .regression import RegressionStatus, classify_regression
from .robustness import analyze_condition_sensitivity, robust_capability_score
from .pareto import pareto_frontier, select_configurations

__all__ = [
    "percentile", "summarize_by", "summarize_latencies", "summarize_scores",
    "bootstrap_correctness_ci", "bootstrap_mean_ci", "paired_comparison", "paired_effect_size",
    "RegressionStatus", "classify_regression", "analyze_condition_sensitivity", "robust_capability_score",
    "pareto_frontier", "select_configurations",
]
