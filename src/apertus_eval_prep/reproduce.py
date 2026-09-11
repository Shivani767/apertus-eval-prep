"""Reproduce a registered experiment from registry metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apertus_eval_prep.registry import load_registry


def verify_reproduction(row: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    """Cross-check a registry row against its artifact. MEASURED evidence only.

    Checks (each independent, all reported):
      artifact_exists   — the run JSON is present.
      blob_vs_registry  — blob.config_hash equals row.config_hash.
      settings_recompute— config_hash recomputed from manifest.settings equals
                          row.config_hash (catches settings/artifact drift).
      accuracy_recompute— overall accuracy recomputed from items equals the
                          registry row (exact); n items equals row overall.n.
      git_commit        — manifest.git_commit equals row.git_commit.

    all_match is False when ANY check fails or artifact is missing. Missing
    data yields match=None (cannot verify), which also fails all_match.
    """
    from apertus_eval_prep.registry import config_hash

    checks: list[dict[str, Any]] = []

    def add(name: str, expected: Any, observed: Any) -> None:
        match = None if observed is None else (expected == observed)
        checks.append({"name": name, "expected": expected,
                       "observed": observed, "match": match})

    path = row.get("path")
    run_path = Path(path) if path and Path(path).is_absolute() else repo_root / (path or "")
    blob = None
    add("artifact_exists", True, run_path.exists())
    if run_path.exists():
        blob = json.loads(run_path.read_text(encoding="utf-8"))
        manifest = blob.get("manifest") or {}
        add("blob_vs_registry", row.get("config_hash"), blob.get("config_hash"))
        settings = manifest.get("settings")
        recomputed = config_hash(settings) if settings else None
        add("settings_recompute", row.get("config_hash"), recomputed)
        add("git_commit", row.get("git_commit"), manifest.get("git_commit"))
        items = blob.get("items") or []
        n = len(items)
        row_overall = row.get("overall") or {}
        row_n = row_overall.get("n")
        add("n_items", row_n, n if items else None)
        if items and row_n:
            acc = sum(1 for it in items if it.get("correct")) / n
            # Registry stores accuracy rounded (e.g. 0.6987 for 559/800 =
            # 0.69875). Compare at the STORED precision so rounding is not
            # reported as a deviation; the exact value is still shown.
            expected = row_overall.get("accuracy")
            s = repr(float(expected)) if expected is not None else ""
            dec = len(s.split(".")[1]) if "." in s else 0
            tol = 0.5 * 10 ** (-dec) + 1e-12
            match = abs(acc - float(expected)) <= tol
            checks.append({"name": "accuracy_recompute", "expected": expected,
                           "observed": round(acc, 10), "match": match,
                           "tolerance": tol,
                           "note": "abs diff at registry storage precision"})
        else:
            add("accuracy_recompute", row_overall.get("accuracy"), None)
    all_match = bool(checks) and all(c["match"] is True for c in checks)
    return {"run_id": row.get("run_id"), "config_hash": row.get("config_hash"),
            "checks": checks, "all_match": all_match,
            "provenance": "MEASURED cross-check of committed artifact vs registry"}


def render_verification_markdown(ver: dict[str, Any]) -> str:
    lines = [
        f"# Reproduction check: {ver['run_id']}",
        "",
        f"config_hash: `{ver['config_hash']}` — "
        f"**{'ALL CHECKS PASS' if ver['all_match'] else 'DEVIATIONS FOUND'}**",
        "",
        "| check | expected | observed | match |",
        "|---|---|---|---|",
    ]
    for c in ver["checks"]:
        obs = c["observed"]
        lines.append(
            f"| {c['name']} | {c['expected']} | {obs} | "
            f"{'yes' if c['match'] is True else 'NO' if c['match'] is False else 'n/a'} |"
        )
    lines.append("")
    lines.append("Deviation report generated from committed artifacts; "
                 "nothing was re-run or re-measured.")
    return "\n".join(lines) + "\n"


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
