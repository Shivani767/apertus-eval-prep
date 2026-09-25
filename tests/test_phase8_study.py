from __future__ import annotations

from pathlib import Path

import pytest

from apertus_eval_prep.core.config import expand_experiment, load_experiment_spec
from apertus_eval_prep.core.errors import ArtifactError, ConfigError
from apertus_eval_prep.core.runner import run_evaluation
from apertus_eval_prep.review.agreement import agreement_summary, cohen_kappa, fleiss_kappa
from apertus_eval_prep.review.export import export_review_package
from apertus_eval_prep.review.ingest import ingest_annotations
from apertus_eval_prep.review.sampling import sample_review_candidates
from apertus_eval_prep.review.schema import ReviewValidationError, validate_annotation
from apertus_eval_prep.study.analysis import analyze_study
from apertus_eval_prep.study.reporting import render_study_html, render_study_markdown, write_study_outputs
from apertus_eval_prep.study.schema import StudySpec, load_study_config
from apertus_eval_prep.utils.serialization import read_json, read_jsonl, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_RUNS = ROOT / "tests/fixtures/phase7_runs"


def test_study_templates_exist_and_validate():
    for name in (
        "PHASE8_STUDY_PROTOCOL.md", "PHASE8_PREREGISTRATION_TEMPLATE.md",
        "PHASE8_DEVIATION_LOG_TEMPLATE.md", "HUMAN_REVIEW_PROTOCOL.md",
        "ANNOTATION_GUIDELINES.md", "TECHNICAL_REPORT_TEMPLATE.md",
        "PORTFOLIO_CASE_STUDY_TEMPLATE.md", "PHASE8_EXECUTION_RUNBOOK.md",
    ):
        assert (ROOT / "docs" / name).stat().st_size > 100
    for name in ("phase8_real_model_study.yaml", "phase8_real_model_study_template.yaml", "phase8_human_review.yaml"):
        spec = load_study_config(ROOT / "configs/studies" / name)
        assert spec.study_id and spec.protocol_path
    mock = load_study_config(ROOT / "configs/studies/phase8_mock_study.yaml")
    assert mock.evidence_mode == "MOCK" and mock.allow_mock is True


def test_real_study_cannot_silently_use_mock_adapter():
    payload = {
        "study": {"study_id": "s", "study_title": "s", "research_question": "q", "evidence_mode": "LOCAL_REAL_MODEL", "matrix": {"models": ["m"]}},
        "base": {"adapter": {"kind": "mock", "model_id": "m"}},
    }
    with pytest.raises(ConfigError, match="real-study config cannot use a mock adapter"):
        StudySpec.from_dict(payload)


def test_study_config_converts_to_existing_matrix_schema():
    spec = load_experiment_spec(ROOT / "configs/studies/phase8_mock_study.yaml")
    cells = expand_experiment(spec)
    assert len(cells) == 12
    assert all(cell.run_spec.experiment_id == "phase8-demo" for cell in cells)
    assert all(cell.run_spec.parent_experiment_id == "phase8-demo" for cell in cells)


def _annotation(identifier: str, reviewer: str, label: str = "correct", *, evidence: str = "LOCAL_REAL_MODEL") -> dict:
    return {
        "annotation_id": identifier, "study_id": "phase8-fixture-study", "run_id": "fixture-real-a",
        "example_id": "item-1", "task": "static_qa", "dimension": "correctness",
        "rubric_version": "phase8-v1", "label": label, "score": 1.0 if label == "correct" else 0.0,
        "confidence": 0.8, "annotator_id_hash": reviewer, "review_timestamp": "2026-01-01T00:00:00Z",
        "sanitized_prompt": "safe prompt", "sanitized_output": "safe output", "notes": "",
        "adjudication_status": "agreed",
        "evidence_references": {
            "evidence_mode": evidence,
            "run_directory": str(FIXTURE_RUNS / "real_a"),
        },
        "status": "completed",
    }


def test_annotation_validation_and_ingest_reject_invalid_or_duplicate(tmp_path):
    assert validate_annotation(_annotation("a", "aaaaaaaaaaaaaaa1"))["status"] == "completed"
    with pytest.raises(ReviewValidationError):
        validate_annotation({**_annotation("bad", "aaaaaaaaaaaaaaa1"), "label": "unknown"})
    path = tmp_path / "annotations.jsonl"
    write_jsonl(path, [_annotation("same", "aaaaaaaaaaaaaaa1"), _annotation("same", "bbbbbbbbbbbbbbb2")])
    with pytest.raises(ReviewValidationError, match="duplicate annotation_id"):
        ingest_annotations(path, tmp_path / "result.json")
    path.write_text("")
    with pytest.raises(ReviewValidationError, match="empty"):
        ingest_annotations(path, tmp_path / "result.json")


def test_human_review_evidence_requires_real_completed_annotations(tmp_path):
    path = tmp_path / "mock.jsonl"
    write_jsonl(path, [_annotation("mock", "aaaaaaaaaaaaaaa1", evidence="MOCK")])
    result = ingest_annotations(path, tmp_path / "mock-result.json")
    assert result["human_reviewed"] is False
    assert result["human_review_status"] == "ANNOTATIONS_ONLY_FOR_SYNTHETIC_EVIDENCE"
    real_path = tmp_path / "real.jsonl"
    write_jsonl(real_path, [_annotation("real-a", "aaaaaaaaaaaaaaa1"), _annotation("real-b", "bbbbbbbbbbbbbbb2")])
    real = ingest_annotations(real_path, tmp_path / "real-result.json")
    assert real["human_reviewed"] is True
    unlinked = _annotation("unlinked", "ccccccccccccccc3")
    unlinked["evidence_references"] = {"evidence_mode": "LOCAL_REAL_MODEL", "run_directory": str(tmp_path / "missing-run")}
    unlinked_path = tmp_path / "unlinked.jsonl"
    write_jsonl(unlinked_path, [unlinked])
    unlinked_result = ingest_annotations(unlinked_path, tmp_path / "unlinked-result.json")
    assert unlinked_result["human_reviewed"] is False
    assert unlinked_result["human_review_status"] == "ANNOTATIONS_ONLY_FOR_SYNTHETIC_EVIDENCE"


def test_agreement_metrics_and_insufficient_behavior():
    records = [_annotation("a1", "aaaaaaaaaaaaaaa1"), _annotation("a2", "bbbbbbbbbbbbbbb2", "incorrect")]
    summary = agreement_summary(records)
    assert summary["overall"]["percent_agreement"]["value"] == 0.0
    assert summary["overall"]["cohen_kappa"]["status"] in {"AVAILABLE", "INCONCLUSIVE"}
    assert summary["overall"]["fleiss_kappa"]["status"] == "INSUFFICIENT_EVIDENCE"
    assert summary["disagreement_queue"]
    assert fleiss_kappa([_annotation(f"x{i}", f"r{i % 3:08x}00000000") for i in range(3)])["status"] == "NOT_AVAILABLE"
    assert cohen_kappa([])["value"] is None


def test_review_sampling_and_export_are_deterministic_and_sanitized(tmp_path):
    from apertus_eval_prep.core.schemas import RunSpec
    base = load_study_config(ROOT / "configs/studies/phase8_mock_study.yaml").base
    run = run_evaluation(RunSpec.from_dict(base), ROOT, output_root=tmp_path / "run")
    first = sample_review_candidates(run.directory, sample_size=2, seed=4)
    second = sample_review_candidates(run.directory, sample_size=2, seed=4)
    assert first == second
    assert all("_priority" not in item for item in first)
    out = tmp_path / "review.jsonl"
    result = export_review_package(
        run.directory, out, dimensions=["correctness", "safety"], sample_size=2,
        study_id="phase8-demo",
    )
    rows = read_jsonl(out)
    assert result["n_items"] == 2 and len(rows) == 4
    assert result["human_reviewed"] is False
    assert all(row["status"] == "template" and "sanitized_prompt" in row for row in rows)


def test_review_export_respects_raw_retention_disabled(tmp_path):
    from apertus_eval_prep.core.config import load_run_spec
    spec = load_run_spec(ROOT / "configs/platform_smoke.yaml")
    spec.reporting.include_raw_outputs = False
    run = run_evaluation(spec, ROOT, output_root=tmp_path / "run")
    out = tmp_path / "review.jsonl"
    export_review_package(run.directory, out, dimensions=["correctness"], sample_size=2)
    text = out.read_text(encoding="utf-8")
    assert "synthetic mock answer" not in text
    assert "RAW_RETENTION_DISABLED" in text


def _fixture_study_spec() -> StudySpec:
    return StudySpec.from_dict({
        "study": {
            "study_id": "phase8-fixture-study", "study_title": "Fixture study",
            "research_question": "q", "evidence_mode": "LOCAL_REAL_MODEL",
            "protocol_path": "docs/PHASE8_STUDY_PROTOCOL.md",
            "deviation_log_path": "docs/PHASE8_DEVIATION_LOG_TEMPLATE.md",
            "matrix": {"models": ["fixture/model-a"]},
        },
        "base": {"adapter": {"kind": "local_transformers", "model_id": "fixture/model-a"}},
        "comparison": {"min_sample_size": 2, "n_boot": 40, "robust_capability_lambda": 0.5},
    })


def test_fixture_study_analysis_refuses_to_claim_real_evidence_and_writes_outputs(tmp_path):
    summary = analyze_study(
        _fixture_study_spec(), [FIXTURE_RUNS / "real_a", FIXTURE_RUNS / "real_b"]
    )
    assert summary["real_model_evidence_available"] is False
    assert "No real-model evidence available" in render_study_markdown(summary)
    assert "Experimental Robust Capability Score" in render_study_markdown(summary)
    assert "<script>" not in render_study_html(
        {"study": {"study_title": "<script>x</script>"}, "rows": []}
    )
    paths = write_study_outputs(summary, tmp_path / "study")
    for name in (
        "study_manifest.json", "study_summary.json", "study_report.md", "study_report.html",
        "comparison_table.csv", "metric_summary.csv", "failure_summary.csv",
        "review_summary.json", "study_limitations.md",
    ):
        assert (tmp_path / "study" / name).exists(), name
    assert set(paths) == {"manifest", "summary", "markdown", "html"}


def test_study_compatibility_rejects_wrong_expected_identity():
    spec = _fixture_study_spec()
    spec.study_id = "different-study"
    with pytest.raises(ArtifactError):
        analyze_study(spec, [FIXTURE_RUNS / "real_a"])


def test_annotation_template_and_schema_are_present():
    assert (ROOT / "data/annotation_templates/phase8_annotation_template.jsonl").exists()
    schema = read_json(ROOT / "data/annotation_templates/phase8_annotation_schema.json")
    assert "sanitized_output" in schema["properties"]
    assert "status" in schema["required"]


def test_cli_review_export_and_ingest(tmp_path, capsys):
    from apertus_eval_prep.cli import main
    from apertus_eval_prep.core.config import load_run_spec
    run = run_evaluation(load_run_spec(ROOT / "configs/platform_smoke.yaml"), ROOT, output_root=tmp_path / "run")
    package = tmp_path / "package.jsonl"
    assert main([
        "platform-export-review", "--run", str(run.directory), "--out", str(package),
        "--dimensions", "correctness", "groundedness", "--sample-size", "2",
        "--study-id", "phase8-demo",
    ]) == 0
    rows = read_jsonl(package)
    completed = []
    for index, row in enumerate(rows):
        dimension = row.get("dimension")
        label = "correct" if dimension == "correctness" else "supported"
        completed.append({
            **row, "status": "completed", "label": label, "score": 1.0,
            "confidence": 0.9, "annotator_id_hash": f"{index + 1:016x}",
            "review_timestamp": "2026-01-01T00:00:00Z",
            "evidence_references": {"evidence_mode": "MOCK"},
        })
    annotations = tmp_path / "completed.jsonl"
    write_jsonl(annotations, completed)
    result = tmp_path / "review.json"
    assert main(["platform-ingest-review", "--input", str(annotations), "--out", str(result), "--study-id", "phase8-demo"]) == 0
    assert read_json(result)["human_reviewed"] is False
    capsys.readouterr()


def test_study_csv_neutralizes_spreadsheet_formulas(tmp_path):
    summary = {
        "manifest": {"study_id": "safe"}, "study": {"study_id": "safe"},
        "rows": [{"run_id": "=HYPERLINK(\"bad\")", "model_id": "+cmd", "evidence_mode": "MOCK"}],
        "limitations": [], "review": {},
    }
    write_study_outputs(summary, tmp_path / "out")
    text = (tmp_path / "out/comparison_table.csv").read_text(encoding="utf-8")
    assert "'=HYPERLINK" in text
    assert "'+cmd" in text
