from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from apertus_eval_prep.core.artifacts import RetentionPolicy, RunStore
from apertus_eval_prep.core.config import expand_experiment, load_experiment_spec, load_run_spec
from apertus_eval_prep.core.errors import ArtifactError, DatasetError
from apertus_eval_prep.core.provenance import prompt_template_hash
from apertus_eval_prep.core.runner import run_evaluation
from apertus_eval_prep.experiments.compare import compare_run_directories
from apertus_eval_prep.experiments.matrix import run_experiment_matrix
from apertus_eval_prep.metrics.paired_comparison import paired_comparison
from apertus_eval_prep.metrics.regression import RegressionStatus, classify_regression
from apertus_eval_prep.metrics.robustness import robust_capability_score
from apertus_eval_prep.release.deployment import CostModel
from apertus_eval_prep.release.gates import GateStatus, evaluate_release_gates
from apertus_eval_prep.safety.risk_scoring import safety_metrics
from apertus_eval_prep.utils.serialization import read_jsonl
from apertus_eval_prep.tasks.perturbations import apply_perturbation
from apertus_eval_prep.tasks.rag_episode import load_episodes
from apertus_eval_prep.tasks.base import load_task_examples
from apertus_eval_prep.utils.hashing import stable_hash
from apertus_eval_prep.utils.logging_utils import StructuredLogger
from apertus_eval_prep.utils.pii import redact_for_artifact, redact_text, redact_text_for_artifact

ROOT = Path(__file__).resolve().parents[1]


def test_schema_preserves_mock_evidence_and_optional_dimensions():
    spec = load_run_spec(ROOT / "configs/platform_smoke.yaml")
    assert spec.evidence_class == "MOCK"
    assert spec.dimensions.language is None


def test_hash_is_stable_for_mapping_order():
    assert stable_hash({"a": 1, "b": [2, 3]}) == stable_hash({"b": [2, 3], "a": 1})


def test_pii_redaction_removes_secret_shape():
    text = redact_text("contact person@example.com with token=abcd1234")
    assert "person@example.com" not in text
    assert "abcd1234" not in text


def test_artifact_store_rejects_escape_and_redacts_credentials(tmp_path):
    store = RunStore.create(tmp_path, run_name="safe", config_hash="cfg", run_id="safe-run")
    store.write_json("nested/data.json", {
        "api_key": "sk-abcdefghijklmnop",
        "nested": {"password": "do-not-store"},
        "command": "python -m x --token=abcdef123456",
    })
    payload = store.read_json("nested/data.json")
    serialized = json.dumps(payload)
    assert payload["api_key"] == "[REDACTED_FIELD]"
    assert "do-not-store" not in serialized
    assert "abcdef123456" not in serialized
    with pytest.raises(ArtifactError):
        store.write_json("../escape.json", {})
    assert redact_text_for_artifact("--token=abcdef123456") != "--token=abcdef123456"
    assert redact_for_artifact({"nested": {"password": "do-not-store"}})["nested"]["password"] == "[REDACTED_FIELD]"


def test_logger_raw_mode_still_redacts_credentials():
    stream = io.StringIO()
    logger = StructuredLogger("test", stream=stream)
    logger.event("debug", allow_raw=True, text="person@example.com", api_key="sk-abcdefghijklmnop")
    record = json.loads(stream.getvalue())
    assert record["text"] == "person@example.com"
    assert record["api_key"] == "[REDACTED_FIELD]"
    assert "sk-abcdefghijklmnop" not in stream.getvalue()


def test_loader_rejects_duplicate_ids(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"id":"x","prompt":"a","gold":"a"}\n{"id":"x","prompt":"b","gold":"b"}\n')
    with pytest.raises(DatasetError):
        load_task_examples(path)


def test_offline_smoke_writes_complete_artifact(tmp_path):
    spec = load_run_spec(ROOT / "configs/platform_smoke.yaml")
    result = run_evaluation(spec, ROOT, output_root=tmp_path, command="test")
    assert result.metrics["evidence_class"] == "MOCK"
    assert result.metrics["quality"]["mean"] == 1.0
    for name in ("manifest.json", "config.resolved.yaml", "dataset.lock.json", "raw_outputs.jsonl",
                 "scored_examples.jsonl", "metrics.json", "confidence_intervals.json", "report.md", "report.html"):
        assert (result.directory / name).exists(), name
    manifest = json.loads((result.directory / "manifest.json").read_text())
    assert manifest["evidence_class"] == "MOCK"
    assert manifest["dataset"]["n_examples"] == 4
    raw = read_jsonl(result.directory / "raw_outputs.jsonl")
    scored = read_jsonl(result.directory / "scored_examples.jsonl")
    assert raw and "request" in raw[0] and "response" in raw[0]
    assert "output_reference" in scored[0] and "output_excerpt" not in scored[0]


def test_matrix_expansion_is_deterministic():
    spec = load_experiment_spec(ROOT / "configs/platform_matrix.yaml")
    first = expand_experiment(spec)
    second = expand_experiment(spec)
    assert len(first) == len(second) == 12
    assert [c.cell_id for c in first] == [c.cell_id for c in second]
    assert first[0].is_baseline


def test_matrix_runs_child_artifacts(tmp_path):
    result = run_experiment_matrix(ROOT / "configs/platform_matrix.yaml", ROOT, output_root=tmp_path)
    assert result.report["experiment_summary"]["n_ok"] >= 10
    assert any(cell.run_id for cell in result.cells)


def test_paired_comparison_and_regression_boundaries():
    report = paired_comparison([0, 0, 1, 1], [0, 1, 1, 1], min_sample_size=2, n_boot=100)
    assert report["n_paired"] == 4
    assert report["delta"] == pytest.approx(0.25)
    assert classify_regression(-0.2, (-0.3, -0.1), n=30) is RegressionStatus.CONFIRMED_REGRESSION
    assert classify_regression(0.0, (-0.01, 0.01), n=30) is RegressionStatus.NO_MEANINGFUL_CHANGE
    assert classify_regression(0.0, (-0.01, 0.01), n=1) is RegressionStatus.INCONCLUSIVE


def test_rcs_reports_components_and_label():
    result = robust_capability_score([0.4, 0.8], lambda_=0.5)
    assert result["experimental"] is True
    assert result["configuration_variance"] == pytest.approx(0.04)
    assert "mean_quality" in result and "limitations" in result


def test_episode_fixture_and_perturbation_are_safe():
    episodes = load_episodes(ROOT / "data/platform_episodes.jsonl")
    assert episodes and episodes[0].initial_context
    changed = apply_perturbation(episodes[0].to_dict(), "remove_key_evidence")
    assert len(changed["initial_context"]) == 0
    assert changed["metadata"]["perturbation"] == "remove_key_evidence"


def test_groundedness_and_tool_sequence_heuristics():
    from apertus_eval_prep.evaluators.groundedness import groundedness_score
    from apertus_eval_prep.evaluators.tool_use import score_tool_sequence, validate_tool_call

    ground = groundedness_score("The policy says two days", [{"source_id": "p", "content": "The policy says two days."}])
    assert ground["score"] > 0.5
    assert score_tool_sequence([{"tool_name": "a"}], ["a"]) ["valid"]
    assert validate_tool_call({"name": "a", "arguments": {}}, [{"name": "a", "input_schema": {"required": ["id"]}}]) ["valid"] is False


def test_safety_metrics_skip_unevaluated_cases():
    results = [
        {"test_id": "ok", "category": "prompt_injection", "severity": "high", "safe": True, "benign": False, "evaluated": True},
        {"test_id": "infra", "category": "prompt_injection", "severity": "high", "safe": None, "benign": False, "evaluated": False},
    ]
    report = safety_metrics(results)
    assert report["n_cases"] == 2
    assert report["n_evaluated"] == 1
    assert report["n_skipped"] == 1
    assert report["attack_success_rate"] == 0.0
    assert report["weighted_risk_score"] == 0.0
    assert report["high_severity_failures"] == 0


def test_safety_metrics_all_skipped_has_no_measured_zero():
    report = safety_metrics([
        {"test_id": "infra", "category": "prompt_injection", "severity": "high", "safe": None, "benign": False, "evaluated": False},
    ])
    assert report["attack_success_rate"] is None
    assert report["weighted_risk_score"] is None
    assert report["high_severity_failures"] is None


def test_relative_fewshot_hash_uses_repo_root(tmp_path):
    spec = load_run_spec(ROOT / "configs/platform_smoke.yaml")
    fewshot = tmp_path / "pack.txt"
    fewshot.write_text("one\ntwo\n", encoding="utf-8")
    spec.prompt.fewshot_path = "pack.txt"
    resolved = prompt_template_hash(spec, tmp_path)
    missing = prompt_template_hash(spec, ROOT / "does-not-exist")
    assert resolved != missing
    assert len(resolved) == 16


def test_cost_model_never_invents_missing_price():
    assert CostModel().estimate(None, None)["quality"] == "UNAVAILABLE"
    assert CostModel(input_per_million=1.0, output_per_million=2.0).estimate(1_000_000, 0)["value"] == 1.0


def test_release_gate_priority_and_missing_evidence():
    metrics = {"safety": {"attack_success_rate": 0.5}}
    decision = evaluate_release_gates(metrics, {"safety": {"max_attack_success_rate": 0.03}})
    assert decision["status"] == GateStatus.BLOCKED_SAFETY.value
    inconclusive = evaluate_release_gates({}, {"performance": {"max_p95_latency_ms": 10}})
    assert inconclusive["status"] == GateStatus.INCONCLUSIVE.value
    zero = evaluate_release_gates(
        {"safety": {"n_cases": 2, "n_evaluated": 2, "attack_success_rate": 0.0}},
        {"safety": {"max_attack_success_rate": 0.0}},
    )
    assert zero["status"] == GateStatus.PASS.value
    malformed = evaluate_release_gates(
        {"quality": {"mean": "not-a-number"}, "n_scored": 1},
        {"quality": {"min_quality": 0.5}},
    )
    assert malformed["status"] == GateStatus.INCONCLUSIVE.value
    explicit_zero_cases = evaluate_release_gates(
        {"safety": {"n_cases": 0, "attack_success_rate": 0.0}},
        {"safety": {"max_attack_success_rate": 0.0}},
    )
    assert explicit_zero_cases["status"] == GateStatus.INCONCLUSIVE.value


def test_episode_runner_writes_tool_trace(tmp_path):
    spec = load_run_spec(ROOT / "configs/platform_agent.yaml")
    result = run_evaluation(spec, ROOT, output_root=tmp_path, command="test-agent")
    assert result.metrics["system"]["episode_count"] == 3
    assert (result.directory / "tool_traces.jsonl").exists()


def test_compare_run_directories_aligns_ids(tmp_path):
    left = run_evaluation(load_run_spec(ROOT / "configs/platform_smoke.yaml"), ROOT, output_root=tmp_path / "left")
    right = run_evaluation(load_run_spec(ROOT / "configs/platform_smoke.yaml"), ROOT, output_root=tmp_path / "right")
    report = compare_run_directories(left.directory, right.directory)
    assert report["n_aligned"] == 4
    assert report["paired"]["n_paired"] == 4


def test_raw_retention_can_be_disabled(tmp_path):
    spec = load_run_spec(ROOT / "configs/platform_smoke.yaml")
    spec.reporting.include_raw_outputs = False
    result = run_evaluation(spec, ROOT, output_root=tmp_path)
    raw = (result.directory / "raw_outputs.jsonl").read_text()
    assert "RAW_RETENTION_DISABLED" in raw
    assert "synthetic mock answer" not in raw


def test_runtime_failure_is_unscored_and_has_no_latency_sample(tmp_path):
    from apertus_eval_prep.adapters.mock import MockAdapter

    result = run_evaluation(
        load_run_spec(ROOT / "configs/platform_smoke.yaml"),
        ROOT,
        adapter=MockAdapter(mode="error"),
        output_root=tmp_path,
    )
    assert result.metrics["n_runtime_failed"] == 4
    assert result.metrics["n_scored"] == 0
    assert result.metrics["quality"]["mean"] is None
    assert result.metrics["latency"]["n_total"] == 0
    assert result.metrics["latency"]["p95_ms"] is None
    failures = read_jsonl(result.directory / "failures.jsonl")
    assert failures and all(item["category"] == "timeout_or_infrastructure_failure" for item in failures)


def test_safety_runtime_failure_is_skipped_evidence(tmp_path):
    from apertus_eval_prep.adapters.mock import MockAdapter
    from apertus_eval_prep.safety.runner import run_safety_evaluation

    result = run_safety_evaluation(
        load_run_spec(ROOT / "configs/platform_safety.yaml"),
        ROOT,
        adapter=MockAdapter(mode="error"),
        output_root=tmp_path,
    )
    safety = result.metrics["safety"]
    assert result.metrics["n_runtime_failed"] == 4
    assert safety["n_cases"] == 4
    assert safety["n_evaluated"] == 0
    assert safety["n_skipped"] == 4
    assert safety["attack_success_rate"] is None
    assert safety["weighted_risk_score"] is None
    failures = read_jsonl(result.directory / "failures.jsonl")
    assert failures and all(item["category"] == "infrastructure_failure" for item in failures)
