from __future__ import annotations

import json
from pathlib import Path

import pytest

from apertus_eval_prep.core.config import expand_experiment, load_experiment_spec, load_run_spec
from apertus_eval_prep.core.errors import ArtifactError, SchemaValidationError
from apertus_eval_prep.core.evidence import evidence_from_manifest, normalize_evidence
from apertus_eval_prep.core.runner import run_evaluation
from apertus_eval_prep.release.deployment import CostModel, compare_deployment_configurations
from apertus_eval_prep.release.gates import RELEASE_GATE_DISCLAIMER
from apertus_eval_prep.release.ingest import ingest_run_directories
from apertus_eval_prep.reporting.html import render_run_html
from apertus_eval_prep.reporting.markdown import render_run_markdown
from apertus_eval_prep.reporting.platform import write_run_reports
from apertus_eval_prep.utils.runtime_profile import detect_runtime_environment, profile_runtime
from apertus_eval_prep.utils.serialization import read_json, write_json

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_RUNS = ROOT / "tests/fixtures/phase7_runs"


def test_evidence_schema_validation_and_legacy_fallback():
    local = normalize_evidence({
        "mode": "LOCAL_REAL_MODEL", "runtime_environment": "google_colab",
        "real_model_execution": True, "hardware_measured": True,
    })
    assert local["mode"] == "LOCAL_REAL_MODEL"
    assert local["real_model_execution"] is True
    with pytest.raises(ValueError):
        normalize_evidence({"mode": "LOCAL_REAL_MODEL", "real_model_execution": False})
    assert evidence_from_manifest({"evidence_class": "MOCK"})["mode"] == "MOCK"
    assert evidence_from_manifest({"evidence_class": "MEASURED"})["mode"] == "UNKNOWN"
    with pytest.raises(SchemaValidationError):
        load_run_spec(ROOT / "configs/platform_smoke.yaml", {"evidence.mode": "NOT_A_MODE"})


def test_evidence_persists_in_mock_run_artifact(tmp_path):
    result = run_evaluation(
        load_run_spec(ROOT / "configs/platform_smoke.yaml"), ROOT,
        output_root=tmp_path, command="phase7-evidence",
    )
    manifest = read_json(result.directory / "manifest.json")
    assert manifest["evidence"]["mode"] == "MOCK"
    assert manifest["evidence"]["real_model_execution"] is False
    assert result.metrics["evidence_mode"] == "MOCK"
    assert result.metrics["synthetic_or_mock"] is True


def test_reports_label_mock_and_local_real_evidence():
    local_manifest = read_json(FIXTURE_RUNS / "real_a/manifest.json")
    local_metrics = read_json(FIXTURE_RUNS / "real_a/metrics.json")
    payload = {"manifest": local_manifest, "metrics": local_metrics, "failures": []}
    markdown = render_run_markdown(payload)
    html = render_run_html(payload)
    assert "LOCAL_REAL_MODEL" in markdown
    assert "\\n>" not in markdown
    assert "Experimental real-model evidence" in markdown
    assert "Hardware measured: `True`" in markdown
    assert RELEASE_GATE_DISCLAIMER in markdown
    assert "LOCAL REAL MODEL" in html and "NOT PRODUCTION APPROVAL" in html
    mock = {"manifest": {"evidence_class": "MOCK"}, "metrics": {}}
    assert "Synthetic/mock evidence" in render_run_markdown(mock)
    assert "MOCK / SYNTHETIC" in render_run_html(mock)


def test_release_gate_always_contains_policy_disclaimer():
    decision = compare_deployment_configurations([])  # import path smoke; no gate claim
    assert "objectives" in decision
    from apertus_eval_prep.release.gates import evaluate_release_gates
    assert evaluate_release_gates({}, {})[ "disclaimer" ] == RELEASE_GATE_DISCLAIMER



def test_local_adapter_optional_dependency_error_and_lazy_mock_path(monkeypatch):
    from apertus_eval_prep.adapters.local_transformers import LocalTransformersAdapter
    from apertus_eval_prep.adapters.base import CompletionRequest
    from apertus_eval_prep.adapters.mock import MockAdapter
    from apertus_eval_prep.core.errors import AdapterModelLoadError

    adapter = LocalTransformersAdapter(
        name="local", model_id="not-loaded", revision=None, seed=1,
        params={"device": "cpu", "dtype": "float32", "quantization": "none"},
    )
    real_import = __import__

    def blocked(name, *args, **kwargs):
        if name == "torch" or name.startswith("transformers"):
            raise ImportError("blocked optional dependency")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", blocked)
    with pytest.raises(AdapterModelLoadError, match="real-model"):
        adapter.complete(CompletionRequest(prompt="hello"))
    mock = MockAdapter.from_params({}, name="mock", model_id="fixture", revision="v1", seed=1)
    assert mock.complete(CompletionRequest(prompt="hello")).simulated is True


def test_runtime_profile_safe_cpu_and_colab_detection(monkeypatch):
    monkeypatch.delenv("COLAB_RELEASE_TAG", raising=False)
    monkeypatch.delenv("COLAB_GPU", raising=False)
    monkeypatch.delenv("COLAB_JUPYTER_IP", raising=False)
    assert detect_runtime_environment() == "local"
    profile = profile_runtime(include_torch=False)
    assert profile["runtime_environment"] == "local"
    assert profile["hardware_measured"] is False
    assert profile["gpu_memory"] is None
    monkeypatch.setenv("COLAB_RELEASE_TAG", "test-release")
    assert detect_runtime_environment() == "google_colab"


def test_colab_configs_validate_without_model_execution():
    for name in ("local_real_model_smoke.yaml", "local_real_model_rag.yaml", "local_real_model_safety.yaml"):
        spec = load_run_spec(ROOT / "configs/colab" / name)
        assert spec.evidence.mode == "LOCAL_REAL_MODEL"
        assert spec.evidence.runtime_environment == "google_colab"
        assert spec.adapter.kind == "local_transformers"
        assert spec.adapter.model_id == "YOUR_MODEL_ID"
    experiment = load_experiment_spec(ROOT / "configs/colab/local_real_model_variance.yaml")
    assert len(expand_experiment(experiment)) == 4


def test_cost_remains_unavailable_without_tokens_or_prices():
    assert CostModel().estimate(None, 20)["value"] is None
    priced = CostModel(input_per_million=1.0, output_per_million=2.0, source="manual")
    assert priced.estimate(None, 20)["quality"] == "UNAVAILABLE"
    assert priced.estimate(1_000_000, 0)["value"] == pytest.approx(1.0)


def test_fixture_artifacts_ingest_and_feed_phase5_selector():
    result = ingest_run_directories([
        FIXTURE_RUNS / "real_a", FIXTURE_RUNS / "real_b"
    ])
    assert result["compatibility"]["compatible"] is True
    assert len(result["points"]) == 2
    assert all(point["evidence_mode"] == "LOCAL_REAL_MODEL" for point in result["points"])
    assert all(point["cost_per_success"] is not None for point in result["points"])
    selection = compare_deployment_configurations(
        result["points"], constraints={"min_quality": 0.9, "max_p95_latency_ms": 100}
    )
    assert selection["selection"]["eligible"]
    assert all(point["label"].startswith("fixture/model-") for point in result["points"])


def test_ingestion_rejects_malformed_and_incompatible_artifacts(tmp_path):
    with pytest.raises(ArtifactError, match="manifest"):
        ingest_run_directories([tmp_path])
    changed = tmp_path / "changed"
    changed.mkdir()
    manifest = read_json(FIXTURE_RUNS / "real_b/manifest.json")
    manifest["dataset_hash"] = "different"
    write_json(changed / "manifest.json", manifest)
    write_json(changed / "metrics.json", read_json(FIXTURE_RUNS / "real_b/metrics.json"))
    with pytest.raises(ArtifactError, match="incompatible"):
        ingest_run_directories([FIXTURE_RUNS / "real_a", changed])
    allowed = ingest_run_directories(
        [FIXTURE_RUNS / "real_a", changed], allow_incompatible=True
    )
    assert allowed["compatibility"]["conflicts"]


def test_fixture_report_generation_is_offline(tmp_path):
    paths = write_run_reports(FIXTURE_RUNS / "real_a", output_dir=tmp_path)
    assert paths["markdown"] and paths["html"]
    text = paths["markdown"].read_text(encoding="utf-8")
    assert "LOCAL_REAL_MODEL" in text
    assert RELEASE_GATE_DISCLAIMER in text
