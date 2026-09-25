"""Config-driven release-gate engine with explicit priority and evidence states."""
from __future__ import annotations

import math
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from apertus_eval_prep.core.errors import GateConfigError
from apertus_eval_prep.utils.pii import redact_for_artifact


_UNCONFIGURED = object()


RELEASE_GATE_DISCLAIMER = (
    "Release-gate results are engineering policy aids and are not production approval."
)


class GateStatus(StrEnum):
    PASS = "PASS"
    PASS_WITH_WATCHLIST = "PASS_WITH_WATCHLIST"
    BLOCKED_SAFETY = "BLOCKED_SAFETY"
    BLOCKED_REGRESSION = "BLOCKED_REGRESSION"
    BLOCKED_QUALITY = "BLOCKED_QUALITY"
    BLOCKED_PERFORMANCE = "BLOCKED_PERFORMANCE"
    BLOCKED_COST = "BLOCKED_COST"
    INCONCLUSIVE = "INCONCLUSIVE"


def _get(mapping: Mapping[str, Any], *path: str) -> Any:
    value: Any = mapping
    for key in path:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value


def _first(*values: Any) -> Any:
    """Return the first present value, preserving measured zeroes."""
    for value in values:
        if value is not None:
            return value
    return None


def _finite_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _ratio(numerator: Any, denominator: Any) -> float | None:
    top = _finite_number(numerator)
    bottom = _finite_number(denominator)
    if top is None or bottom is None or bottom == 0:
        return None
    return top / bottom


def evaluate_release_gates(metrics: Mapping[str, Any], rules: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Evaluate versioned quality, safety, regression, and deployment rules.

    Required checks with missing measurements produce ``INCONCLUSIVE``; only a
    measured threshold violation produces a blocking status.  This prevents a
    missing cost or latency field from being treated as zero cost.
    """
    if rules is None:
        rules = {}
    if not isinstance(rules, Mapping):
        raise GateConfigError("release-gate rules must be a mapping")
    rules = dict(rules)
    safety = _mapping(rules.get("safety"))
    quality = _mapping(rules.get("quality"))
    performance = _mapping(rules.get("performance"))
    confidence_rules = _mapping(rules.get("confidence"))
    groundedness_rules = _mapping(rules.get("groundedness"))
    agent_rules = _mapping(rules.get("agent"))
    sample_rules = _mapping(rules.get("sample_size"))
    regression = _mapping(rules.get("regression"))
    cost = _mapping(rules.get("cost"))
    reasons: list[str] = []
    watchlist: list[str] = []
    checks: list[dict[str, Any]] = []
    watchlist_config = rules.get("watchlist")
    if isinstance(watchlist_config, list):
        watchlist.extend(str(item) for item in watchlist_config if str(item).strip())
    elif watchlist_config:
        watchlist.append(str(watchlist_config))
    safety_metrics = _mapping(_get(metrics, "safety"))

    def check(name: str, value: Any, limit: Any, mode: str) -> bool | None | object:
        if limit is None:
            return _UNCONFIGURED
        if mode not in {"max", "min"}:
            raise GateConfigError(f"unsupported gate mode: {mode!r}")
        numeric_limit = _finite_number(limit)
        if numeric_limit is None:
            raise GateConfigError(f"{name}: limit must be a finite number")
        if value is None:
            result = "INCONCLUSIVE"
            passed = None
            reasons.append(f"{name}: insufficient evidence")
        else:
            numeric_value = _finite_number(value)
            if numeric_value is None:
                result = "INCONCLUSIVE"
                passed = None
                reasons.append(f"{name}: evidence is not a finite number")
            else:
                passed = numeric_value <= numeric_limit if mode == "max" else numeric_value >= numeric_limit
                result = "PASS" if passed else "FAIL"
                if not passed:
                    reasons.append(f"{name}={value} violates {mode} {limit}")
        checks.append({"name": name, "value": value, "limit": limit, "mode": mode, "result": result})
        return passed

    # Preserve the historical API: a supplied safety rate is usable even when
    # older runners did not record n_cases. An explicit zero-case record is not
    # usable evidence, because a measured zero must have an observed denominator.
    safety_case_count = _finite_number(safety_metrics.get("n_cases"))
    safety_evaluated_count = _finite_number(safety_metrics.get("n_evaluated"))
    if safety_evaluated_count is not None:
        safety_has_cases = safety_evaluated_count > 0
    else:
        safety_has_cases = safety_case_count is None or safety_case_count > 0

    def safety_value(name: str) -> Any:
        return safety_metrics.get(name) if safety_has_cases else None

    safety_checks = [
        check("attack_success_rate", safety_value("attack_success_rate"), safety.get("max_attack_success_rate"), "max"),
        check("benign_false_refusal_rate", safety_value("benign_false_refusal_rate"), safety.get("max_benign_false_refusal_rate"), "max"),
        check("high_severity_failures", safety_value("high_severity_failures"), safety.get("max_high_severity_failures"), "max"),
        check("weighted_risk_score", safety_value("weighted_risk_score"), safety.get("max_weighted_risk_score"), "max"),
    ]
    regression_status = _first(
        regression.get("status"),
        _get(metrics, "regression", "status"),
        _get(metrics, "baseline_comparison", "status"),
    )
    if regression_status in {"CONFIRMED_REGRESSION", "LIKELY_REGRESSION"}:
        reasons.append(f"regression status={regression_status}")
    n_total = _first(_get(metrics, "n_total"), _get(metrics, "quality", "n_total"))
    n_failed = _first(_get(metrics, "n_failed"), _get(metrics, "quality", "n_failed"))
    quality_mean = _first(_get(metrics, "quality", "mean"), _get(metrics, "quality", "accuracy"))
    groundedness = _first(
        _get(metrics, "system", "groundedness_mean"),
        _get(metrics, "groundedness", "mean"),
        _get(metrics, "deployment", "groundedness"),
    )
    tool_schema = _first(_get(metrics, "system", "tool_schema_validity"), _get(metrics, "tool_use", "schema_validity_rate"))
    agent_success = _first(
        _get(metrics, "system", "task_completion_rate"),
        _get(metrics, "system", "agent_success_rate"),
        _get(metrics, "deployment", "agent_success"),
    )
    agent_reliability = _first(
        _get(metrics, "system", "agent_reliability"),
        _get(metrics, "deployment", "agent_reliability"),
        _ratio(_get(metrics, "n_scored"), n_total),
    )
    robustness = _first(
        _get(metrics, "robustness_score"),
        _get(metrics, "deployment", "robustness_score"),
    )
    variance = _first(_get(metrics, "quality", "variance"), _get(metrics, "quality", "std"))
    failure_rate = _first(_get(metrics, "failure_rate"), _get(metrics, "deployment", "failure_rate"), _ratio(n_failed, n_total))
    error_rate = _first(_get(metrics, "error_rate"), _get(metrics, "deployment", "error_rate"), _ratio(_get(metrics, "n_runtime_failed"), n_total))
    timeout_rate = _first(_get(metrics, "timeout_rate"), _get(metrics, "deployment", "timeout_rate"))
    latency_mean = _first(_get(metrics, "latency", "mean_ms"), _get(metrics, "deployment", "latency_mean_ms"))
    latency_p50 = _first(_get(metrics, "latency", "p50_ms"), _get(metrics, "deployment", "latency_p50_ms"))
    latency_p95 = _first(_get(metrics, "latency", "p95_ms"), _get(metrics, "deployment", "latency_p95_ms"))
    cost_per_success = _first(_get(metrics, "deployment", "cost_per_success"), _get(metrics, "cost", "value"))
    cost_value = _first(_get(metrics, "deployment", "cost_value"), _get(metrics, "cost", "value"))
    quality_checks = [
        check("quality", quality_mean, quality.get("min_quality"), "min"),
        check("groundedness", groundedness, groundedness_rules.get("min_groundedness", quality.get("min_groundedness")), "min"),
        check("tool_schema_validity", tool_schema, quality.get("min_tool_schema_validity"), "min"),
        check("agent_success", agent_success, agent_rules.get("min_success"), "min"),
        check("agent_reliability", agent_reliability, agent_rules.get("min_reliability"), "min"),
        check("robustness", robustness, quality.get("min_robustness"), "min"),
        check("sample_size", _get(metrics, "n_scored"), quality.get("min_sample_size", sample_rules.get("min_n_scored")), "min"),
        check("variance", variance, performance.get("max_variance"), "max"),
    ]
    performance_checks = [
        check("mean_latency_ms", latency_mean, performance.get("max_mean_latency_ms"), "max"),
        check("p50_latency_ms", latency_p50, performance.get("max_p50_latency_ms"), "max"),
        check("p95_latency_ms", latency_p95, performance.get("max_p95_latency_ms"), "max"),
        check("failure_rate", failure_rate, performance.get("max_failure_rate"), "max"),
        check("error_rate", error_rate, performance.get("max_error_rate"), "max"),
        check("timeout_rate", timeout_rate, performance.get("max_timeout_rate"), "max"),
    ]
    cost_checks = [
        check("cost_per_success", cost_per_success, cost.get("max_cost_per_success"), "max"),
        check("total_cost", cost_value, cost.get("max_total_cost"), "max"),
    ]
    quality_ci = _mapping(_get(metrics, "confidence_intervals", "quality_mean"))
    confidence_checks = [
        check("quality_ci_lower_bound", quality_ci.get("lo"),
              confidence_rules.get("min_lower_bound"), "min"),
        check("quality_ci_width", (quality_ci["hi"] - quality_ci["lo"])
              if _finite_number(quality_ci.get("lo")) is not None and _finite_number(quality_ci.get("hi")) is not None
              else quality_ci.get("width"), confidence_rules.get("max_width"), "max"),
    ]
    all_results = safety_checks + quality_checks + performance_checks + cost_checks + confidence_checks
    has_failure = any(result is False for result in all_results)
    has_missing = any(result is None for result in all_results)
    if has_failure and any(result is False for result in safety_checks):
        status = GateStatus.BLOCKED_SAFETY
    elif regression_status in {"CONFIRMED_REGRESSION", "LIKELY_REGRESSION"}:
        status = GateStatus.BLOCKED_REGRESSION
    elif any(result is False for result in quality_checks):
        status = GateStatus.BLOCKED_QUALITY
    elif any(result is False for result in performance_checks):
        status = GateStatus.BLOCKED_PERFORMANCE
    elif any(result is False for result in cost_checks):
        status = GateStatus.BLOCKED_COST
    elif has_missing:
        status = GateStatus.INCONCLUSIVE
    elif not checks:
        status = GateStatus.PASS_WITH_WATCHLIST if watchlist else GateStatus.INCONCLUSIVE
        if not watchlist:
            reasons.append("no release-gate rules configured")
    else:
        status = GateStatus.PASS_WITH_WATCHLIST if watchlist else GateStatus.PASS
    safe_report = redact_for_artifact({
        "status": status.value, "reasons": reasons, "watchlist": watchlist,
        "checks": checks, "rules": rules,
        "disclaimer": RELEASE_GATE_DISCLAIMER,
        "limitations": [RELEASE_GATE_DISCLAIMER,
                        "automated gates are not a safety certification"],
    })
    return safe_report


def load_gate_rules(path: str | Path) -> dict[str, Any]:
    """Load a versioned gate YAML file with a clear configuration error."""
    from pathlib import Path
    from apertus_eval_prep.core.errors import GateConfigError
    from apertus_eval_prep.utils.serialization import read_yaml
    try:
        payload = read_yaml(Path(path))
    except Exception as exc:
        raise GateConfigError(f"unable to load release-gate rules: {path}") from exc
    if not isinstance(payload, dict):
        raise GateConfigError("release-gate rules must be a mapping")
    return payload.get("release_gates", payload)


__all__ = ["RELEASE_GATE_DISCLAIMER", "GateStatus", "evaluate_release_gates", "load_gate_rules"]
