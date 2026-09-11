"""Tests for reproduction deviation checks (verify_reproduction)."""

import json

from apertus_eval_prep.registry import config_hash
from apertus_eval_prep.reproduce import render_verification_markdown, verify_reproduction

SETTINGS = {"model_id": "m", "seed": 0, "backend": "hf"}


def _write_run(tmp_path, accuracy=0.5, n=4, correct=2, git="g" * 40,
               settings=None):
    settings = dict(SETTINGS if settings is None else settings)
    items = [{"id": f"it{i}", "correct": i < correct} for i in range(n)]
    blob = {
        # the runner computes blob.config_hash from manifest.settings —
        # fixtures must do the same or settings_recompute cannot pass
        "config_hash": config_hash(settings),
        "manifest": {"git_commit": git, "settings": settings},
        "items": items,
        "overall": {"n": n, "correct": correct, "accuracy": accuracy},
    }
    p = tmp_path / "run.json"
    p.write_text(json.dumps(blob), encoding="utf-8")
    return p, blob


def _row(p, config_hash_val, accuracy=0.5, n=4, git="g" * 40):
    return {"run_id": "r1", "config_hash": config_hash_val, "path": str(p),
            "git_commit": git, "overall": {"n": n, "accuracy": accuracy}}


def test_matching_artifact_passes_all_checks(tmp_path):
    p, blob = _write_run(tmp_path)
    ver = verify_reproduction(_row(p, blob["config_hash"]), tmp_path)
    assert ver["all_match"] is True
    names = {c["name"]: c["match"] for c in ver["checks"]}
    assert all(m is True for m in names.values())
    assert names["settings_recompute"] is True  # recomputed hash matches
    assert names["accuracy_recompute"] is True  # 2/4 = 0.5 exact


def test_registry_rounding_is_not_a_deviation(tmp_path):
    # 559/800 = 0.69875 stored as 0.6987 -> stored-precision comparison
    p, blob = _write_run(tmp_path, n=800, correct=559, accuracy=0.6987)
    ver = verify_reproduction(
        _row(p, blob["config_hash"], accuracy=0.6987, n=800), tmp_path)
    acc = {c["name"]: c for c in ver["checks"]}["accuracy_recompute"]
    assert acc["match"] is True
    assert acc["observed"] == 0.69875  # exact value still reported


def test_real_deviation_is_detected(tmp_path):
    p, blob = _write_run(tmp_path, accuracy=0.5)  # artifact says 0.5
    ver = verify_reproduction(_row(p, blob["config_hash"], accuracy=0.9),
                              tmp_path)  # registry says 0.9
    acc = {c["name"]: c for c in ver["checks"]}["accuracy_recompute"]
    assert acc["match"] is False
    assert ver["all_match"] is False
    md = render_verification_markdown(ver)
    assert "DEVIATIONS FOUND" in md


def test_settings_drift_detected(tmp_path):
    p, blob = _write_run(tmp_path)
    # tamper with the artifact settings so the recomputed hash no longer
    # matches the stored digest (as if the artifact were edited post-hoc)
    blob["manifest"]["settings"]["seed"] = 7
    p.write_text(json.dumps(blob), encoding="utf-8")
    ver = verify_reproduction(_row(p, blob["config_hash"]), tmp_path)
    sc = {c["name"]: c for c in ver["checks"]}["settings_recompute"]
    assert sc["match"] is False
    assert ver["all_match"] is False


def test_missing_artifact_fails_closed(tmp_path):
    p, blob = _write_run(tmp_path)
    ver = verify_reproduction(_row(tmp_path / "gone.json", blob["config_hash"]),
                              tmp_path)
    assert ver["all_match"] is False
    first = ver["checks"][0]
    assert first["name"] == "artifact_exists" and first["match"] is False


def test_real_committed_artifact_verifies():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    registry = root / "results" / "registry_paper.jsonl"
    rows = [json.loads(l) for l in registry.read_text().splitlines() if l.strip()]
    row = next(r for r in rows if r.get("config_hash") == "17c798b9a52bef83"
               and (root / (r.get("path") or "")).exists())
    ver = verify_reproduction(row, root)
    assert ver["all_match"] is True, ver["checks"]