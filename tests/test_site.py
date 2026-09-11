"""Tests for the frontend export (site.json): provenance + no-fabrication."""

from pathlib import Path

from apertus_eval_prep.registry import load_registry
from apertus_eval_prep.site import (
    build_ranking_comparisons,
    build_rankings,
    build_site,
    cell_from_row,
)


def _repo(tmp: Path) -> Path:
    return Path(__file__).resolve().parents[1]


def test_export_matches_registry():
    root = _repo(Path())
    site = build_site(root, root / "results/registry_paper.jsonl",
                      n_boot=50, n_perm=50, seed=0)
    rows = load_registry(root / "results/registry_paper.jsonl")
    assert site["schema_version"] == 1
    assert site["coverage"]["n_rows"] == len(rows)
    assert site["coverage"]["planned_cells"] == 34
    assert len(site["cells"]) == len(rows)
    # every cell is traceable to its registry row
    ids = {r["run_id"] for r in rows}
    assert {c["run_id"] for c in site["cells"]} == ids
    # measured accuracy never invented: matches the row overall exactly
    by_id = {r["run_id"]: r for r in rows}
    for c in site["cells"]:
        exp = (by_id[c["run_id"]].get("overall") or {}).get("accuracy")
        assert (c["accuracy"] is None and exp is None) or abs(c["accuracy"] - exp) < 1e-9


def test_pending_cell_is_flagged_not_zeroed(tmp_path):
    row = {"run_id": "r-missing", "model_id": "m/x", "factor": "control",
           "factor_level": "control", "status": "ok", "overall": {},
           "config_hash": "abc", "path": "results/runs/nope.json"}
    cell = cell_from_row(row, None, tmp_path)
    assert cell["status"] == "PENDING" or cell["provenance"] == "PENDING"
    assert cell["accuracy"] is None


def test_ranking_reversal_flags():
    rank = None
    import json as _json

    root = _repo(Path())
    site = build_site(root, root / "results/registry_paper.jsonl",
                      n_boot=50, n_perm=50, seed=0)
    five = [c for c in site["ranking_comparisons"]
            if c["variant_key"] == "prompt_id=5shot"]
    assert five, "no control-vs-5shot comparison in real data"
    assert five[0]["reordered"] is True
    assert abs(five[0]["tau"] - 1 / 3) < 1e-4  # Qwen/Phi swap: 1 of 3 pairs


def test_ers_excludes_single_cell_model():
    root = _repo(Path())
    site = build_site(root, root / "results/registry_paper.jsonl",
                      n_boot=50, n_perm=50, seed=0)
    r = site["reliability"]
    assert "Qwen/Qwen2.5-7B-Instruct" in r["excluded_models"]
    assert len(r["models"]) == 3
    assert r["components"]["config_stability"] is not None
    assert r["n_components"] == 3  # seed_stability still unavailable
    assert r["provisional"] is True