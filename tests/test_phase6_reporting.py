from __future__ import annotations

import json
from pathlib import Path

import pytest

from apertus_eval_prep.core.config import load_run_spec
from apertus_eval_prep.core.runner import run_evaluation
from apertus_eval_prep.cli import main as cli_main
from apertus_eval_prep.reporting.html import render_run_html
from apertus_eval_prep.reporting.markdown import render_run_markdown
from apertus_eval_prep.reporting.platform import load_report_payload, write_failure_fingerprint, write_run_reports
from apertus_eval_prep.release.failures import FAILURE_CATEGORIES, FAILURE_RECORD_FIELDS, failure_fingerprint, normalize_failure_record, normalize_failure_records
from apertus_eval_prep.utils.serialization import read_jsonl

ROOT = Path(__file__).resolve().parents[1]


def _failure(**overrides):
    row = {"failure_id": "run:1", "run_id": "run", "example_id": "1", "task": "qa", "category": "incorrect_answer", "failure_type": "incorrect_answer", "subcategory": "wrong_answer", "severity": "high", "sanitized_input_excerpt": "safe input", "sanitized_output_excerpt": "safe output", "condition_labels": ["prompt-sensitive"], "error": None}
    row.update(overrides)
    return row


def test_failure_schema_normalization_and_sanitization():
    row = normalize_failure_record(_failure(sanitized_input_excerpt="contact person@example.com", error="token=abcd1234"), manifest={"run_id": "run", "model": {"model_id": "m", "adapter_kind": "mock"}, "backend": {"device": "cpu"}})
    assert set(FAILURE_RECORD_FIELDS).issubset(row)
    assert "person@example.com" not in json.dumps(row)
    assert "abcd1234" not in json.dumps(row)
    assert row["backend"] == "mock"
    assert row["schema_version"] == "1.0"
    assert "incorrect_answer" in FAILURE_CATEGORIES


def test_failure_fingerprint_aggregates_categories_severity_and_priorities():
    rows = normalize_failure_records([
        _failure(failure_id="a", failure_type="unsafe_completion", category="prompt_injection", severity="critical"),
        _failure(failure_id="b", failure_type="incorrect_answer", category="incorrect_answer", severity="low"),
        _failure(failure_id="c", failure_type="tool_recovery_failure", category="tool_recovery_failure", severity="medium", condition_labels=["backend-sensitive"]),
    ])
    profile = failure_fingerprint(rows, total=10)
    assert profile["n_failures"] == 3
    assert profile["failure_rate"] == pytest.approx(0.3)
    assert profile["by_failure_type"]["unsafe_completion"] == 1
    assert profile["by_severity"]["critical"] == 1
    assert profile["safety_critical_failures"] == 1
    assert profile["investigation_priorities"][0]["priority"] == "P0"
    assert "observed pattern" in json.dumps(profile["priority_rules"])


def test_failure_fingerprint_missing_denominator_and_baseline_delta():
    missing = failure_fingerprint([_failure()])
    assert missing["failure_rate"] is None
    baseline = failure_fingerprint([_failure()], total=10)
    candidate = failure_fingerprint([_failure(), _failure(failure_id="b")], total=10, baseline_fingerprint=baseline)
    assert candidate["baseline_comparison"]["status"] == "OBSERVED_DELTA"
    assert candidate["baseline_comparison"]["category_deltas"]["incorrect_answer"] == 1


def test_markdown_and_html_are_escaped_and_include_required_sections():
    rows = normalize_failure_records([_failure(sanitized_input_excerpt="<script>alert(1)</script>")])
    payload = {"manifest": {"run_id": "r", "evidence_class": "MOCK", "model": {"model_id": "m"}, "backend": {"device": "cpu"}, "entrypoint_command": "python -m eval --token=abcd1234"}, "metrics": {"n_total": 2, "n_failed": 1, "quality": {"mean": 0.5, "n_scored": 2}, "confidence_intervals": {"quality_mean": {"lo": 0.1, "hi": 0.9}}, "release_gate": {"status": "INCONCLUSIVE", "reasons": ["missing"]}}, "failures": rows, "failure_fingerprint": failure_fingerprint(rows, total=2)}
    md = render_run_markdown(payload)
    html = render_run_html(payload)
    assert "MOCK" in md and "Failure fingerprint" in md and "Missing evidence" in md
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "MOCK / SYNTHETIC" in html
    assert "Quality and confidence" in html and "Failure fingerprint" in html


def test_report_and_fingerprint_helpers_write_artifacts(tmp_path):
    result = run_evaluation(load_run_spec(ROOT / "configs/platform_smoke.yaml"), ROOT, output_root=tmp_path, command="phase6-test")
    fingerprint_path, profile = write_failure_fingerprint(result.directory)
    assert fingerprint_path.exists()
    assert profile["schema_version"] == "1.0"
    paths = write_run_reports(result.directory, report_format="both", output_dir=tmp_path / "reports")
    assert (tmp_path / "reports" / "report.md").exists()
    assert (tmp_path / "reports" / "report.html").exists()
    assert paths["markdown"] and paths["html"]
    for name in ("manifest.json", "config.resolved.yaml", "raw_outputs.jsonl", "scored_examples.jsonl", "metrics.json", "confidence_intervals.json", "failures.jsonl", "failure_fingerprint.json", "report.md", "report.html"):
        assert (result.directory / name).exists(), name


def test_report_payload_marks_mock_and_preserves_missing_sections(tmp_path):
    result = run_evaluation(load_run_spec(ROOT / "configs/platform_smoke.yaml"), ROOT, output_root=tmp_path)
    payload = load_report_payload(result.directory)
    assert payload["manifest"]["evidence_class"] == "MOCK"
    assert "system" not in payload["metrics"]
    assert "safety" not in payload["metrics"]
    report = render_run_markdown(payload)
    assert "Unavailable" in report or "unavailable" in report
    assert read_jsonl(result.directory / "failures.jsonl") is not None



def test_platform_report_and_fingerprint_cli(tmp_path):
    result = run_evaluation(load_run_spec(ROOT / "configs/platform_smoke.yaml"), ROOT, output_root=tmp_path, command="phase6-cli")
    assert cli_main(["platform-fingerprint", "--run", str(result.directory)]) == 0
    assert cli_main(["platform-report", "--run", str(result.directory), "--format", "both", "--out", str(tmp_path / "cli-reports")]) == 0
    assert (tmp_path / "cli-reports" / "report.md").exists()
    assert (tmp_path / "cli-reports" / "report.html").exists()
