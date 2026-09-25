from __future__ import annotations

from pathlib import Path

import pytest

from apertus_eval_prep.core.config import load_run_spec
from apertus_eval_prep.core.runner import run_evaluation
from apertus_eval_prep.metrics.pareto import pareto_frontier, select_configurations
from apertus_eval_prep.release.deployment import (
    CostModel,
    compare_deployment_configurations,
    summarize_deployment,
)
from apertus_eval_prep.release.gates import GateStatus, evaluate_release_gates, load_gate_rules
from apertus_eval_prep.utils.serialization import read_json

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / "data/phase5_points.json"
CONSTRAINTS = ROOT / "data/phase5_constraints.json"
GATES = ROOT / "configs/release_gates/phase5.yaml"


def _points():
    return read_json(POINTS)["points"]


def test_cost_model_is_config_driven_and_never_invents_unavailable_prices():
    assert CostModel().estimate(None, None)["quality"] == "UNAVAILABLE"
    assert CostModel().estimate(100, 20)["quality"] == "UNAVAILABLE"
    assert CostModel().estimate(-1, 20)["quality"] == "UNAVAILABLE"
    assert CostModel().estimate(float("nan"), 20)["quality"] == "UNAVAILABLE"
    with pytest.raises(ValueError):
        CostModel(input_per_million=-1)
    with pytest.raises(ValueError):
        CostModel(output_per_million=float("inf"))
    priced = CostModel(
        input_per_million=1.0, output_per_million=2.0, source="test fixture"
    ).estimate(1_000_000, 500_000)
    assert priced["quality"] == "DERIVED_ESTIMATE"
    assert priced["value"] == pytest.approx(2.0)
    assert priced["source"] == "test fixture"


def test_deployment_summary_uses_success_count_and_exposes_missing_evidence():
    metrics = {
        "n_total": 4, "n_successful": 2, "n_failed": 2, "n_runtime_failed": 1, "n_timeout": 1,
        "quality": {"mean": 0.8, "variance": 0.01, "n_scored": 4},
        "latency": {"mean_ms": 100, "p50_ms": 110, "p95_ms": 120},
        "usage": {"input_tokens": 1000, "output_tokens": 200},
        "safety": {"category_pass_rate": 0.9, "attack_success_rate": 0.1},
        "system": {"groundedness_mean": 0.85, "task_completion_rate": 0.8},
        "backend": "mock", "device": "cpu", "precision": "auto", "quantization": "none",
    }
    result = summarize_deployment(
        metrics, cost_model=CostModel(input_per_million=1, output_per_million=2)
    )
    assert result["cost_per_success"] == pytest.approx(0.0007)
    assert result["cost_per_success_status"] == "DERIVED_ESTIMATE"
    assert result["error_rate"] == pytest.approx(0.25)
    assert result["timeout_rate"] == pytest.approx(0.25)
    assert result["agent_reliability"] == pytest.approx(0.5)
    assert result["backend"] == "mock"
    unavailable = summarize_deployment(metrics)
    assert unavailable["cost_per_success"] is None
    assert unavailable["cost_per_success_status"] == "UNAVAILABLE"


def test_pareto_frontier_explains_domination_and_excludes_missing_evidence():
    result = pareto_frontier(_points(), {
        "quality": "max", "safety": "max", "groundedness": "max",
        "robustness": "max", "latency_p95_ms": "min", "cost": "min", "variance": "min",
    })
    assert {point["label"] for point in result["frontier"]} == {
        "mock-baseline", "mock-high-quality", "mock-efficient"
    }
    missing = next(point for point in result["excluded"] if point["label"] == "mock-missing-cost")
    assert missing["missing_objectives"] == ["cost"]
    assert missing["reason"] == "missing or non-finite objective value"
    assert all(point["reason"] for point in result["frontier"])



def _gate_metrics(**overrides):
    metrics = {
        "n_total": 4, "n_successful": 4, "n_scored": 4, "n_failed": 0,
        "n_runtime_failed": 0, "n_timeout": 0, "robustness_score": 0.8,
        "quality": {"mean": 0.9, "variance": 0.01, "n_scored": 4},
        "system": {"groundedness_mean": 0.9, "task_completion_rate": 0.9},
        "safety": {"n_cases": 4, "n_evaluated": 4, "attack_success_rate": 0.0},
        "latency": {"mean_ms": 100, "p50_ms": 110, "p95_ms": 120},
        "deployment": {"cost_per_success": 0.01, "cost_value": 0.04, "error_rate": 0.0, "timeout_rate": 0.0},
        "confidence_intervals": {"quality_mean": {"lo": 0.8, "hi": 1.0}},
    }
    metrics.update(overrides)
    return metrics


def test_gate_precedence_and_watchlist_are_deterministic():
    rules = load_gate_rules(GATES)
    assert evaluate_release_gates(_gate_metrics(), rules)["status"] == GateStatus.PASS.value
    assert evaluate_release_gates(
        _gate_metrics(safety={"n_cases": 4, "n_evaluated": 4, "attack_success_rate": 0.5}),
        {"safety": {"max_attack_success_rate": 0.01}},
    )["status"] == GateStatus.BLOCKED_SAFETY.value
    assert evaluate_release_gates(
        _gate_metrics(), {"quality": {"min_quality": 0.95}}
    )["status"] == GateStatus.BLOCKED_QUALITY.value
    assert evaluate_release_gates(
        _gate_metrics(), {"performance": {"max_p95_latency_ms": 10}}
    )["status"] == GateStatus.BLOCKED_PERFORMANCE.value
    assert evaluate_release_gates(
        _gate_metrics(), {"cost": {"max_cost_per_success": 0.001}}
    )["status"] == GateStatus.BLOCKED_COST.value
    assert evaluate_release_gates(
        _gate_metrics(), {"watchlist": ["review this deployment"]}
    )["status"] == GateStatus.PASS_WITH_WATCHLIST.value
    assert evaluate_release_gates(
        _gate_metrics(), {"quality": {"min_quality": 0.5}, "cost": {"max_cost_per_success": 0.001}}
    )["status"] == GateStatus.BLOCKED_COST.value


def test_phase5_run_writes_cost_deployment_and_gate_artifacts(tmp_path):
    spec = load_run_spec(ROOT / "configs/platform_phase5_deployment.yaml")
    result = run_evaluation(spec, ROOT, output_root=tmp_path, command="phase5-test")
    metrics = result.metrics
    assert metrics["evidence_class"] == "MOCK"
    assert metrics["deployment"]["cost_per_success"] is not None
    assert metrics["deployment"]["cost_per_success_status"] == "DERIVED_ESTIMATE"
    assert metrics["deployment"]["cost_status"] == "DERIVED_ESTIMATE"
    assert metrics["n_successful"] >= 0
    assert metrics["release_gate"]["status"] in {
        GateStatus.PASS.value,
        GateStatus.INCONCLUSIVE.value,
        GateStatus.BLOCKED_QUALITY.value,
        GateStatus.BLOCKED_PERFORMANCE.value,
        GateStatus.BLOCKED_COST.value,
        GateStatus.BLOCKED_SAFETY.value,
    }
    assert metrics["release_gate"]["reasons"]
    for name in ("config.resolved.yaml", "metrics.json", "gate_report.json", "report.md"):
        assert (result.directory / name).exists()


def test_phase5_fixture_json_is_deterministic():
    first = read_json(POINTS)
    second = read_json(POINTS)
    assert first == second
    assert len(first["points"]) == 4
    assert all(point["evidence_class"] == "MOCK" for point in first["points"])


def test_selector_resolves_aliases_and_reports_rejections_and_pareto_options():
    result = compare_deployment_configurations(
        _points(), constraints=read_json(CONSTRAINTS)
    )
    selection = result["selection"]
    assert selection["status"] == "UNIQUE_ELIGIBLE"
    assert selection["recommendation"]["label"] == "mock-efficient"
    assert {point["label"] for point in selection["pareto_optimal"]} == {"mock-efficient"}
    rejected = {point["label"]: point for point in selection["rejected"]}
    assert any("maximum" in reason for reason in rejected["mock-high-quality"]["rejection_reasons"])
    assert any("maximum" in reason for reason in rejected["mock-baseline"]["rejection_reasons"])
    assert any("insufficient evidence" in reason for reason in rejected["mock-missing-cost"]["rejection_reasons"])


def test_selector_returns_insufficient_evidence_when_no_point_can_be_evaluated():
    result = select_configurations(
        [{"label": "missing", "quality": None}], {"min_quality": 0.5}
    )
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["recommendation"] is None
    assert result["insufficient_evidence"] is True
