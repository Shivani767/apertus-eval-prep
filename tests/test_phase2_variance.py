from __future__ import annotations

import json
from pathlib import Path

import pytest

from apertus_eval_prep.core.config import expand_experiment, load_experiment_spec
from apertus_eval_prep.experiments.matrix import run_experiment_matrix
from apertus_eval_prep.metrics.aggregate import summarize_scores
from apertus_eval_prep.metrics.confidence_intervals import bootstrap_mean_ci
from apertus_eval_prep.metrics.paired_comparison import paired_comparison, paired_effect_size
from apertus_eval_prep.metrics.regression import RegressionStatus, classify_regression
from apertus_eval_prep.metrics.robustness import analyze_condition_sensitivity, robust_capability_score

ROOT = Path(__file__).resolve().parents[1]


def test_aggregate_metrics_and_bootstrap_are_deterministic_with_missing_values():
    values = [0.0, 1.0, 1.0, None, "bad", float("nan"), 0.5]
    summary = summarize_scores(values, total=10, failed=2)
    assert summary["count"] == 4
    assert summary["mean"] == pytest.approx(0.625)
    assert summary["median"] == pytest.approx(0.75)
    assert summary["min"] == 0.0
    assert summary["max"] == 1.0
    assert summary["std"] == pytest.approx(0.41457810)
    assert summary["standard_error"] == pytest.approx(0.20728905)
    assert summary["missing_or_invalid"] == 4
    first = bootstrap_mean_ci([0.0, 1.0, 1.0, 0.5], n_boot=80, seed=4)
    second = bootstrap_mean_ci([0.0, 1.0, 1.0, 0.5], n_boot=80, seed=4)
    assert first == second
    assert first["lo"] <= first["mean"] <= first["hi"]
    edge = bootstrap_mean_ci([0.0, 1.0], n_boot=20, alpha=1.0, seed=1)
    assert edge["lo"] == 0.0 and edge["hi"] == 1.0


def test_paired_comparison_reports_effect_and_missing_evidence():
    baseline = {"a": 0.0, "b": 1.0, "c": 0.5, "d": None}
    candidate = {"a": 0.2, "b": 0.8, "c": 0.5, "e": 1.0, "bad": "x"}
    result = paired_comparison(
        baseline, candidate, n_boot=120, seed=2,
        practical_effect_threshold=0.05, min_sample_size=2,
    )
    assert result["n_paired"] == 3
    assert result["n_invalid_candidate"] == 1
    assert result["n_dropped"] >= 2
    assert result["effect_size_valid"] is True
    assert result["effect_size"] is not None
    assert result["status"] in {status.value for status in RegressionStatus}
    assert paired_comparison([0.0, 1.0], [0.2, 0.8], n_boot=20, alpha=1.0)["ci_low"] is not None
    assert paired_effect_size([0.0, 0.0], [1.0, 1.0]) is None


@pytest.mark.parametrize(
    ("delta", "interval", "expected"),
    [
        (-0.4, (-0.5, -0.3), RegressionStatus.CONFIRMED_REGRESSION),
        (-0.1, (-0.15, -0.01), RegressionStatus.LIKELY_REGRESSION),
        (0.0, (-0.01, 0.01), RegressionStatus.NO_MEANINGFUL_CHANGE),
        (0.1, (0.01, 0.15), RegressionStatus.LIKELY_IMPROVEMENT),
        (0.4, (0.3, 0.5), RegressionStatus.CONFIRMED_IMPROVEMENT),
        (0.1, (-0.2, 0.3), RegressionStatus.INCONCLUSIVE),
    ],
)
def test_regression_status_boundaries(delta, interval, expected):
    assert classify_regression(
        delta, interval, n=40, practical_effect_threshold=0.05, min_sample_size=20
    ) is expected


def test_rcs_reports_components_and_experimental_label():
    result = robust_capability_score([0.4, 0.8, 0.6], lambda_=0.5)
    assert result["mean_quality"] == pytest.approx(0.6)
    assert result["configuration_variance"] == pytest.approx(0.0266666667)
    assert result["score"] == pytest.approx(0.5866666667)
    assert result["lambda"] == 0.5
    assert result["experimental"] is True
    assert result["limitations"]


def test_condition_sensitivity_names_stable_and_sensitive_failures():
    rows = [
        {"example_id": "stable-good", "score": 1.0, "correct": True, "prompt_template": "a", "backend": "mock", "quantization": "none"},
        {"example_id": "stable-good", "score": 1.0, "correct": True, "prompt_template": "b", "backend": "mock", "quantization": "none"},
        {"example_id": "stable-bad", "score": 0.0, "correct": False, "prompt_template": "a", "backend": "mock", "quantization": "none"},
        {"example_id": "stable-bad", "score": 0.0, "correct": False, "prompt_template": "b", "backend": "mock", "quantization": "none"},
        {"example_id": "prompt-bad", "score": 1.0, "correct": True, "prompt_template": "a", "backend": "mock", "quantization": "none"},
        {"example_id": "prompt-bad", "score": 0.0, "correct": False, "prompt_template": "b", "backend": "mock", "quantization": "none"},
    ]
    result = analyze_condition_sensitivity(
        rows, ["prompt_template", "backend", "quantization"], n_boot=40, seed=1
    )
    assert result["stable_success"] == 1
    assert result["stable_failure"] == 1
    assert result["representative_sensitive_failures"][0]["classification"] == "prompt_sensitive_failure"
    assert "prompt_template" in result["unstable_conditions"]


def test_condition_sensitivity_covers_backend_and_quantization_labels():
    rows = [
        {"example_id": "backend-sensitive", "score": 1.0, "correct": True, "prompt_template": "a", "backend": "cpu", "quantization": "none"},
        {"example_id": "backend-sensitive", "score": 0.0, "correct": False, "prompt_template": "a", "backend": "gpu", "quantization": "none"},
        {"example_id": "quant-sensitive", "score": 1.0, "correct": True, "prompt_template": "a", "backend": "cpu", "quantization": "none"},
        {"example_id": "quant-sensitive", "score": 0.0, "correct": False, "prompt_template": "a", "backend": "cpu", "quantization": "int4"},
    ]
    result = analyze_condition_sensitivity(rows, ["prompt_template", "backend", "quantization"], n_boot=20, seed=2)
    classes = {item["classification"] for item in result["condition_sensitive"]}
    assert "backend_sensitive_failure" in classes
    assert "quantization_sensitive_failure" in classes


def _small_matrix_config(tmp_path: Path) -> Path:
    path = tmp_path / "matrix.yaml"
    path.write_text(
        """
experiment:
  name: phase2-small
  id: phase2-small
  base:
    adapter:
      kind: mock
      model_id: synthetic/mock-oracle-v1
      revision: fixture-v1
      params: {mode: normal, skill: 0.8, fail_rate: 0.0, seed_jitter: 0.05, prompt_penalties: {strict: 0.1}}
    task: {kind: static_qa, path: data/platform_smoke.jsonl, tasks: [platform_qa], limit: 4}
    prompt: {prompt_id: phase2, version: v1, template: base}
    decoding: {seed: 1, temperature: 0.0, top_p: 1.0, max_new_tokens: 16}
    metrics: {n_boot: 40, seed: 1}
    reporting: {output_dir: runs/phase2, markdown: true, html: true}
    evidence_class: MOCK
  baseline: {seed: 1, temperature: 0.0, top_p: 1.0, prompt_template: base, model_revision: fixture-v1, backend: mock, precision: auto, quantization: none, task: static_qa, dataset: data/platform_smoke.jsonl, split: null}
  factors:
    seed: [1, 2]
    temperature: [0.0, 0.2]
    prompt_template: [base, strict]
    model_revision: [fixture-v1]
    backend: [mock]
    precision: [auto]
    quantization: [none]
    task: [static_qa]
    dataset: [data/platform_smoke.jsonl]
    split: [null]
  max_runs: 8
  comparison: {practical_effect_threshold: 0.02, min_sample_size: 2, n_boot: 40, seed: 1, robust_capability_lambda: 0.5}
""".strip() + "\n",
        encoding="utf-8",
    )
    return path


def test_small_mock_matrix_creates_child_artifacts_and_report(tmp_path):
    config_path = _small_matrix_config(tmp_path)
    result = run_experiment_matrix(config_path, ROOT, output_root=tmp_path / "runs", command="phase2-test")
    assert len(result.cells) == 8
    assert result.report["parent_experiment_id"] == "phase2-small"
    assert result.report["experiment_summary"]["n_ok"] == 8
    assert result.report["robust_capability_score"]["experimental"] is True
    assert "confidence_intervals" in result.report
    assert "baseline_vs_first_candidate" in result.report
    for cell in result.cells:
        assert cell.status == "ok"
        assert cell.run_id and cell.directory
        assert cell.parent_experiment_id == "phase2-small"
        assert cell.resolved_config_path
        directory = Path(cell.directory)
        assert (directory / "manifest.json").exists()
        assert (directory / "config.resolved.yaml").exists()
        assert (directory / "metrics.json").exists()
        assert (directory / "report.md").exists()
    report = (tmp_path / "runs" / "phase2-small.experiment.md").read_text(encoding="utf-8")
    for section in ("Factor breakdown", "Confidence intervals", "Robust Capability Score", "Unstable conditions", "Representative sensitive failures"):
        assert section in report


def test_matrix_factor_aliases_are_declarative():
    spec = load_experiment_spec(ROOT / "configs/platform_matrix.yaml")
    cells = expand_experiment(spec)
    assert len(cells) == 12
    assert {"prompt_template", "model_revision", "backend", "precision", "quantization", "dataset", "split"}.issubset(spec.factors)
    assert all(cell.run_spec.experiment_id == "platform-variance" for cell in cells)
    assert all(cell.run_spec.parent_experiment_id == "platform-variance" for cell in cells)
    assert any(cell.conditions.get("prompt_template") == "strict" for cell in cells)
