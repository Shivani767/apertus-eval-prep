"""Cost and latency evaluator interfaces."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from apertus_eval_prep.metrics.aggregate import summarize_latencies
from apertus_eval_prep.release.deployment import CostModel, summarize_deployment


def evaluate_cost_latency(records: Sequence[Mapping[str, Any]], *, cost_model: CostModel | None = None) -> dict[str, Any]:
    latencies = [row.get("latency_ms") for row in records]
    input_tokens = sum(int(row.get("input_tokens") or 0) for row in records)
    output_tokens = sum(int(row.get("output_tokens") or 0) for row in records)
    metrics = {"latency": summarize_latencies(latencies), "input_tokens": input_tokens, "output_tokens": output_tokens}
    metrics.update(summarize_deployment(metrics, cost_model=cost_model))
    return metrics


__all__ = ["evaluate_cost_latency"]
