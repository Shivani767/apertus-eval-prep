import json
from pathlib import Path

from apertus_eval_prep.reproduce import find_registry_row, reproduction_plan


def test_find_registry_row_by_run_id(tmp_path: Path):
    reg = tmp_path / "r.jsonl"
    row = {"run_id": "abc_control", "config_hash": "deadbeef", "status": "ok", "model_id": "org/m"}
    reg.write_text(json.dumps(row) + "\n", encoding="utf-8")
    found = find_registry_row(reg, run_id="abc_control")
    assert found["config_hash"] == "deadbeef"


def test_reproduction_plan_includes_commands(tmp_path: Path):
    reg = tmp_path / "r.jsonl"
    row = {
        "run_id": "M_control_control_abcd1234",
        "config_hash": "abcd1234",
        "status": "ok",
        "model_id": "HuggingFaceTB/SmolLM2-1.7B-Instruct",
        "factor": "control",
        "factor_level": "control",
        "path": "results/runs/x.json",
    }
    reg.write_text(json.dumps(row) + "\n", encoding="utf-8")
    plan = reproduction_plan(row, tmp_path)
    assert "sweep" in plan["sweep_command"]
    assert plan["model_id"] == "HuggingFaceTB/SmolLM2-1.7B-Instruct"
