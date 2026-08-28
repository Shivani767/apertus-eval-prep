"""Reproduce a registered experiment from registry metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apertus_eval_prep.registry import load_registry


def find_registry_row(
    registry_path: Path,
    *,
    config_hash: str | None = None,
    run_id: str | None = None,
    experiment_id: str | None = None,
) -> dict[str, Any] | None:
    rows = load_registry(registry_path)
    if run_id:
        for row in rows:
            if row.get("run_id") == run_id:
                return row
    if config_hash:
        for row in rows:
            if row.get("config_hash") == config_hash:
                return row
    if experiment_id:
        ok_rows = [r for r in rows if r.get("experiment_id") == experiment_id and r.get("status") == "ok"]
        return ok_rows[-1] if ok_rows else None
    return None


def reproduction_plan(row: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    """Return manifest summary and the closest CLI command to replay this cell."""
    path = row.get("path")
    run_path = Path(path) if path and Path(path).is_absolute() else repo_root / (path or "")
    manifest = {}
    settings = {}
    if run_path.exists():
        blob = json.loads(run_path.read_text(encoding="utf-8"))
        manifest = blob.get("manifest") or {}
        settings = manifest.get("settings") or {}

    factor = row.get("factor", "control")
    factor_level = row.get("factor_level", "control")
    model_id = row.get("model_id") or settings.get("model_id")

    # Best-effort sweep replay (paper matrix cells).
    cmd_parts = [
        "python -m apertus_eval_prep sweep",
        "--config configs/experiments/stability.yaml",
        "--profile t4",
        f"--out-dir results/runs",
        f"--registry results/registry_paper.jsonl",
    ]
    if model_id:
        cmd_parts.append(f"--only-model {model_id}")
    if factor and factor != "control":
        cmd_parts.append(f"--only-factor {factor}")
    cmd_parts.append("--force")

    single_eval = [
        "python -m apertus_eval_prep eval",
        "--config configs/default.yaml",
        f"--model-id {model_id}" if model_id else "",
        f"--out {path or 'results/replay.json'}",
    ]
    for key in ("backend", "chat_template", "quantization", "prompt_id", "seed", "temperature"):
        val = settings.get(key)
        if val is not None:
            flag = key.replace("_", "-")
            single_eval.append(f"--{flag} {val}")

    return {
        "run_id": row.get("run_id"),
        "config_hash": row.get("config_hash"),
        "experiment_id": row.get("experiment_id"),
        "factor": factor,
        "factor_level": factor_level,
        "model_id": model_id,
        "path": str(path),
        "git_commit": manifest.get("git_commit") or row.get("git_commit"),
        "hardware": manifest.get("hardware") or row.get("hardware"),
        "settings": settings,
        "overall": row.get("overall"),
        "sweep_command": " ".join(p for p in cmd_parts if p),
        "eval_command_hint": " ".join(p for p in single_eval if p),
        "note": (
            "Sweep command replays the OFAT cell via stability.yaml. "
            "For canary runs use eval with the YAML named in settings.data_path. "
            "Hardware and git commit must match for strict reproduction."
        ),
    }


def render_reproduction_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Reproduction plan",
        "",
        f"**run_id:** `{plan.get('run_id')}`",
        f"**config_hash:** `{plan.get('config_hash')}`",
        f"**model:** `{plan.get('model_id')}`",
        f"**factor:** `{plan.get('factor')}` = `{plan.get('factor_level')}`",
        f"**git_commit:** `{plan.get('git_commit')}`",
        f"**result path:** `{plan.get('path')}`",
        "",
        "## Sweep replay (paper matrix)",
        "",
        "```bash",
        plan.get("sweep_command", ""),
        "```",
        "",
        "## Single-eval hint (canary / custom YAML)",
        "",
        "```bash",
        plan.get("eval_command_hint", ""),
        "```",
        "",
        plan.get("note", ""),
        "",
    ]
    return "\n".join(lines)
