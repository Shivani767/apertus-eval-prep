"""Provider-independent deployment cost, latency, and selection abstractions."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from apertus_eval_prep.metrics.pareto import pareto_frontier, select_configurations


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _ratio(numerator: Any, denominator: Any) -> float | None:
    top, bottom = _number(numerator), _number(denominator)
    return top / bottom if top is not None and bottom not in (None, 0.0) else None


def _canonical_point(point: Mapping[str, Any]) -> dict[str, Any]:
    item = dict(point)
    aliases = {
        "quality": ("quality", "quality_score", "task_score"),
        "safety": ("safety", "safety_score"),
        "groundedness": ("groundedness", "groundedness_score"),
        "robustness": ("robustness", "robustness_score", "rcs"),
        "latency_p95_ms": ("latency_p95_ms", "p95_latency_ms", "p95_ms"),
        "latency_p50_ms": ("latency_p50_ms", "p50_latency_ms", "p50_ms"),
        "latency_mean_ms": ("latency_mean_ms", "mean_latency_ms", "mean_ms"),
        "cost": ("cost", "cost_per_success", "cost_value"),
        "variance": ("variance", "quality_variance"),
    }
    for canonical, candidates in aliases.items():
        value = _first(*(item.get(candidate) for candidate in candidates))
        if isinstance(value, Mapping):
            value = _first(value.get("value"), value.get("score"))
        item[canonical] = value
    if item.get("safety") is None and item.get("attack_success_rate") is not None:
        try:
            item["safety"] = 1.0 - float(item["attack_success_rate"])
        except (TypeError, ValueError):
            item["safety"] = None
    for canonical, candidate in (("error_rate", "error"), ("timeout_rate", "timeout")):
        if item.get(canonical) is None and item.get(candidate) is not None:
            item[canonical] = item[candidate]
    return item


DEFAULT_OBJECTIVES: dict[str, str] = {
    "quality": "max",
    "safety": "max",
    "groundedness": "max",
    "robustness": "max",
    "latency_p95_ms": "min",
    "cost": "min",
    "variance": "min",
}


@dataclass(frozen=True)
class CostModel:
    """Manual/config-driven prices; no provider prices are embedded here."""

    input_per_million: float | None = None
    output_per_million: float | None = None
    currency: str = "USD"
    source: str = "manual configuration"
    effective_date: str | None = None
    estimate_label: str = "DERIVED_ESTIMATE"

    def __post_init__(self) -> None:
        for name, value in (
            ("input_per_million", self.input_per_million),
            ("output_per_million", self.output_per_million),
        ):
            if value is None:
                continue
            if isinstance(value, bool):
                raise ValueError(f"{name} must be finite and non-negative")
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} must be finite and non-negative") from exc
            if not math.isfinite(number) or number < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if not str(self.currency).strip():
            raise ValueError("currency must not be empty")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "CostModel":
        data = dict(raw or {})
        return cls(
            input_per_million=data.get("input_per_million", data.get("input_cost_per_million")),
            output_per_million=data.get("output_per_million", data.get("output_cost_per_million")),
            currency=str(data.get("currency", "USD")),
            source=str(data.get("source", "manual configuration")),
            effective_date=data.get("effective_date"),
            estimate_label=str(data.get("estimate_label", "DERIVED_ESTIMATE")),
        )

    def estimate(self, input_tokens: int | None, output_tokens: int | None) -> dict[str, Any]:
        """Estimate only when usage and every applicable price are known."""
        token_values: dict[str, int | None] = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        invalid = []
        for name, value in token_values.items():
            if value is None:
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                invalid.append(name)
                continue
            if not math.isfinite(number) or number < 0:
                invalid.append(name)
        if invalid:
            return {
                "value": None,
                "currency": self.currency,
                "quality": "UNAVAILABLE",
                "source": self.source,
                "reason": "token usage invalid",
                "components": {},
                "missing": invalid,
            }
        if input_tokens is None and output_tokens is None:
            return {"value": None, "currency": self.currency, "quality": "UNAVAILABLE",
                    "source": self.source, "reason": "token usage unavailable",
                    "components": {}, "missing": ["input_tokens", "output_tokens"]}
        if input_tokens is None or output_tokens is None:
            missing = [name for name, value in (("input_tokens", input_tokens), ("output_tokens", output_tokens))
                       if value is None]
            return {"value": None, "currency": self.currency, "quality": "UNAVAILABLE",
                    "source": self.source, "reason": "token usage incomplete",
                    "components": {}, "missing": missing}
        components = {
            "input": float(input_tokens) / 1_000_000.0 * float(self.input_per_million) if self.input_per_million is not None else None,
            "output": float(output_tokens) / 1_000_000.0 * float(self.output_per_million) if self.output_per_million is not None else None,
        }
        missing = [name for name, value in components.items() if value is None]
        if missing:
            return {"value": None, "currency": self.currency, "quality": "UNAVAILABLE",
                    "source": self.source, "reason": "configured token price missing",
                    "components": components, "missing": missing}
        value = float(components["input"] or 0.0) + float(components["output"] or 0.0)
        return {"value": value, "currency": self.currency, "quality": "DERIVED_ESTIMATE",
                "source": self.source, "estimate": True, "estimate_label": self.estimate_label,
                "effective_date": self.effective_date, "components": components, "missing": []}


def summarize_deployment(metrics: Mapping[str, Any], *, cost_model: CostModel | None = None) -> dict[str, Any]:
    """Extract comparable deployment dimensions without inventing evidence."""
    quality = _mapping(metrics.get("quality"))
    latency = _mapping(metrics.get("latency"))
    usage = _mapping(metrics.get("usage"))
    system = _mapping(metrics.get("system"))
    safety = _mapping(metrics.get("safety"))
    deployment = _mapping(metrics.get("deployment"))
    cost = (cost_model or CostModel()).estimate(usage.get("input_tokens"), usage.get("output_tokens"))
    successful = _first(metrics.get("n_successful"), metrics.get("n_successes"), quality.get("n_successful"))
    successful_number = _number(successful)
    cost_value = _number(cost.get("value"))
    cost_per_success = cost_value / successful_number if cost_value is not None and successful_number not in (None, 0.0) else None
    attack_success = _number(safety.get("attack_success_rate"))
    safety_score = _first(safety.get("safety_score"), safety.get("category_pass_rate"))
    safety_method = "reported" if safety_score is not None else None
    if safety_score is None and attack_success is not None:
        safety_score, safety_method = 1.0 - attack_success, "one_minus_attack_success_rate"
    n_total = _first(metrics.get("n_total"), quality.get("n_total"))
    n_failed = _first(metrics.get("n_failed"), quality.get("n_failed"))
    n_runtime = _first(metrics.get("n_runtime_failed"), metrics.get("n_error"))
    n_timeout = _first(metrics.get("n_timeout"), metrics.get("n_timeouts"))
    robustness = _first(
        metrics.get("robustness"), metrics.get("robustness_score"),
        _mapping(metrics.get("robust_capability_score")).get("score"),
        system.get("robustness"), system.get("robustness_score"),
    )
    reliability = _first(system.get("agent_reliability"), system.get("reliability"), metrics.get("agent_reliability"))
    if reliability is None:
        reliability = _ratio(metrics.get("n_successful"), n_total)
    agent_success = _first(system.get("task_completion_rate"), system.get("agent_success_rate"), metrics.get("agent_success_rate"))
    evidence = _mapping(metrics.get("evidence"))
    evidence_mode = _first(metrics.get("evidence_mode"), evidence.get("mode"))
    evidence_mode = str(evidence_mode) if evidence_mode is not None else None
    runtime_profile = _mapping(metrics.get("runtime_profile"))
    return {
        "quality": quality.get("mean"), "quality_score": quality.get("mean"), "task_score": quality.get("mean"),
        "n_scored": quality.get("n_scored"), "n_total": n_total, "n_successful": successful,
        "robustness_score": robustness, "robustness": robustness,
        "safety": safety_score, "safety_score": safety_score, "attack_success_rate": attack_success,
        "safety_score_method": safety_method, "groundedness": _first(system.get("groundedness_mean"), metrics.get("groundedness"), system.get("groundedness")),
        "groundedness_score": _first(system.get("groundedness_mean"), metrics.get("groundedness"), system.get("groundedness")),
        "agent_success": agent_success, "agent_success_rate": agent_success,
        "agent_reliability": reliability, "reliability": reliability,
        "latency_mean_ms": _first(latency.get("mean_ms"), latency.get("mean")),
        "latency_p50_ms": _first(latency.get("p50_ms"), latency.get("p50")),
        "latency_p95_ms": _first(latency.get("p95_ms"), latency.get("p95")),
        "throughput": _first(latency.get("throughput"), metrics.get("throughput")),
        "variance": _first(quality.get("variance"), metrics.get("variance"), quality.get("std")),
        "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
        "tokens_in": usage.get("input_tokens"), "tokens_out": usage.get("output_tokens"),
        "cost": cost, "cost_value": cost.get("value"), "cost_per_success": cost_per_success,
        "cost_per_success_status": "DERIVED_ESTIMATE" if cost_per_success is not None else "UNAVAILABLE",
        "cost_status": cost.get("quality"),
        "backend": metrics.get("backend"), "device": metrics.get("device"),
        "model_id": metrics.get("model_id"), "model_revision": metrics.get("model_revision"),
        "tokenizer_id": metrics.get("tokenizer_id"), "tokenizer_revision": metrics.get("tokenizer_revision"),
        "precision": metrics.get("precision"), "quantization": metrics.get("quantization"),
        "memory_measurement": metrics.get("memory_measurement"),
        "runtime_profile": runtime_profile or None,
        "hardware_profile": runtime_profile or None,
        "error_rate": _first(metrics.get("error_rate"), _ratio(n_runtime, n_total)),
        "timeout_rate": _first(metrics.get("timeout_rate"), _ratio(n_timeout, n_total)),
        "failure_rate": _first(metrics.get("failure_rate"), _ratio(n_failed, n_total)),
        "run_failures": metrics.get("n_failed"), "runtime_failures": n_runtime,
        "evidence_class": metrics.get("evidence_class"), "evidence_mode": evidence_mode,
        "evidence": evidence or None, "cost_config": _mapping(metrics.get("cost_config")) or None,
        "known_limitations": list(metrics.get("known_limitations") or evidence.get("known_limitations") or []),
        "deployment": deployment,
    }


def compare_deployment_configurations(
    points: Sequence[Mapping[str, Any]], *, constraints: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Return multi-objective frontier and optional constraint selection."""
    normalized = [_canonical_point(point) for point in points]
    result: dict[str, Any] = {
        "objectives": dict(DEFAULT_OBJECTIVES),
        "points": normalized,
        "pareto": pareto_frontier(normalized, DEFAULT_OBJECTIVES),
    }
    if constraints is not None:
        result["selection"] = select_configurations(
            normalized, constraints, objectives=DEFAULT_OBJECTIVES
        )
        result["status"] = result["selection"]["recommendation_status"]
    else:
        result["status"] = "NO_CONSTRAINTS"
    return result


__all__ = ["CostModel", "summarize_deployment", "compare_deployment_configurations"]
