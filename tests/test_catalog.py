"""Catalog tests — synthetic files only (hermetic), sha256 determinism."""

import hashlib
import json
from pathlib import Path

import pytest

from apertus_eval_prep.catalog import (
    SOURCES_META,
    build_catalog,
    combined_eval_set_record,
    dataset_record,
    measure_jsonl,
    model_record,
    sha256_file,
)


def _write_jsonl(path: Path, rows):
    path.write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )


def _make_official_dir(tmp_path: Path) -> Path:
    d = tmp_path / "official"
    d.mkdir()
    # one real-shaped file per SOURCES_META task
    for task, meta in SOURCES_META.items():
        rows = [
            {"id": f"{task}/{i}", "task": task,
             "language": "en" if task != "mgsm" else ["en", "de", "fr"][i % 3],
             "gold": "A", "prompt": f"q{i}"}
            for i in range(4)
        ]
        _write_jsonl(d / meta["file"], rows)
    combined = [
        {"id": f"combined/{i}", "task": "x", "language": "en", "gold": "B",
         "prompt": "p"} for i in range(6)
    ]
    _write_jsonl(d / "eval_set.jsonl", combined)
    return d


def test_measure_jsonl_counts_and_languages(tmp_path):
    p = tmp_path / "slice.jsonl"
    _write_jsonl(p, [
        {"id": "a", "task": "t1", "language": "en"},
        {"id": "b", "task": "t1", "language": "hi"},
        {"id": "a", "task": "t1", "language": "en"},  # duplicate id -> counted
    ])
    m = measure_jsonl(p)
    assert m["n_items"] == 3
    assert m["languages"] == ["en", "hi"]
    assert m["n_duplicate_ids"] == 1
    assert m["tasks"] == ["t1"]


def test_sha256_matches_hashlib(tmp_path):
    p = tmp_path / "f.txt"
    p.write_bytes(b"apertus")
    assert sha256_file(p) == hashlib.sha256(b"apertus").hexdigest()


def test_dataset_record_measured_fields(tmp_path):
    d = _make_official_dir(tmp_path)
    rec = dataset_record(d, "gsm8k")
    assert rec["status"] == "MEASURED"
    assert rec["dataset_id"] == "openai/gsm8k:test"
    assert rec["content_sha256"] == sha256_file(d / "gsm8k.jsonl")
    assert rec["measured"]["n_items"] == 4
    assert rec["source"]["license"] == "MIT"
    # hub revision recorded in SOURCES_META, content hash measured here
    assert rec["source"]["hub_revision"].startswith("740312")


def test_dataset_record_missing_file_is_unavailable(tmp_path):
    rec = dataset_record(tmp_path, "arc_easy")  # no files created
    assert rec["status"] == "UNAVAILABLE"
    assert rec["content_sha256"] is None
    assert rec["measured"] is None


def test_combined_eval_set_record(tmp_path):
    d = _make_official_dir(tmp_path)
    rec = combined_eval_set_record(d)
    assert rec["status"] == "MEASURED"
    assert rec["measured"]["n_items"] == 6
    assert rec["content_sha256"] == sha256_file(d / "eval_set.jsonl")


def test_model_record_derived_from_registry():
    rows = [
        {"model_id": "m/a", "backend": "hf", "quantization": None,
         "factor": "control", "factor_level": "control", "status": "ok",
         "run_id": "r1"},
        {"model_id": "m/a", "backend": "hf", "quantization": "int8",
         "factor": "quantization", "factor_level": "int8", "status": "ok",
         "run_id": "r2"},
        {"model_id": "m/b", "backend": "vllm", "quantization": None,
         "factor": "backend", "factor_level": "vllm", "status": "ok",
         "run_id": "r3", "revision": "abc123"},
    ]
    a = model_record("m/a", rows)
    assert a["revision"] is None and a["revision_status"] == "UNAVAILABLE"
    assert a["param_count"] is None  # never guessed from the name
    assert a["measured_backends"] == ["hf"]
    assert a["measured_quantizations"] == ["int8"]  # control carries no field
    assert a["n_registry_cells"] == 2
    b = model_record("m/b", rows)
    assert b["revision"] == "abc123" and b["revision_status"] == "MEASURED"
    # model whose only row is a control row: 'none' (no quantization) is what
    # was measured — but a model with NO rows measures nothing at all.
    only_control = model_record("m/a", [rows[0]])
    assert only_control["measured_quantizations"] == ["none"]
    assert only_control["n_registry_cells"] == 1
    assert model_record("m/missing", rows)["n_registry_cells"] == 0
    assert model_record("m/missing", rows)["measured_quantizations"] == []


def test_model_record_uses_artifact_settings(tmp_path):
    """Real-registry shape: backend/quantization live in manifest.settings."""
    from apertus_eval_prep.catalog import artifact_settings_by_run

    rows = [
        {"model_id": "m/x", "factor": "control", "factor_level": "control",
         "status": "ok", "run_id": "r1", "path": "runs/r1.json"},
        {"model_id": "m/x", "factor": "quantization", "factor_level": "int4",
         "status": "ok", "run_id": "r2", "path": "runs/r2.json"},
        {"model_id": "m/x", "factor": "backend", "factor_level": "vllm",
         "status": "ok", "run_id": "r3", "path": "runs/missing.json"},
    ]
    runs = tmp_path / "runs"
    runs.mkdir()
    # exactly like the committed control blobs: quantization is the STRING none
    (runs / "r1.json").write_text(json.dumps(
        {"manifest": {"settings": {"backend": "hf", "quantization": "none"}}}))
    (runs / "r2.json").write_text(json.dumps(
        {"manifest": {"settings": {"backend": "hf", "quantization": "int4"}}}))

    arts = artifact_settings_by_run(tmp_path, rows)
    assert set(arts) == {"r1", "r2"}  # missing artifact absent, not imputed
    rec = model_record("m/x", rows, arts)
    assert rec["measured_backends"] == ["hf"]
    assert rec["measured_quantizations"] == ["int4", "none"]
    assert rec["n_registry_cells"] == 3  # missing artifact still a known cell
    assert rec["revision"] is None  # artifacts recorded revision: None
    # each unique path read once: cache is stable across calls
    assert artifact_settings_by_run(tmp_path, rows) == arts


def test_build_catalog_end_to_end(tmp_path):
    d = _make_official_dir(tmp_path)
    reg = tmp_path / "reg.jsonl"
    _write_jsonl(reg, [
        {"model_id": "m/a", "backend": "hf", "factor": "control",
         "factor_level": "control", "status": "ok", "run_id": "r1"},
    ])
    cat = build_catalog(tmp_path, reg)
    assert cat["schema_version"] == 1
    assert len(cat["datasets"]) == 5  # 4 tasks + combined
    assert cat["models"][0]["model_id"] == "m/a"
    # deterministic across calls (fingerprints, not timestamps)
    cat2 = build_catalog(tmp_path, reg)
    assert cat == cat2
