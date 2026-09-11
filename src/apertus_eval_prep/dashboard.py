"""Research dashboard: one aggregate view over the committed registry.

Sections (all derived from committed artifacts; nothing re-measured):
  coverage    — MEASURED / SAMPLED / PENDING row counts (status taxonomy).
  models      — per-model measured cells, mean/min/max accuracy.
  ers         — Evaluation Reliability Score over the all-cells matrix
                (DERIVED, provisional; same logic as the `ers` command).
  deviations  — verify_reproduction over every row whose artifact exists:
                hash recomputation, accuracy at stored precision, git SHA.
  failures    — optional failure taxonomy over explicitly listed run files.

Missing data is reported, never zero-filled: rows without artifacts are
PENDING and count as verification failures (fail closed).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apertus_eval_prep.registry import load_registry
from apertus_eval_prep.reliability import evaluation_reliability_score
from apertus_eval_prep.reproduce import verify_reproduction
from apertus_eval_prep.result_schema import (
    MEASURED,
    PENDING,
    SAMPLED,
    classify_row,
)


def _ers_section(rows: list[dict[str, Any]], *, n_boot: int, seed: int) -> dict[str, Any] | None:
    """ERS over the all-cells matrix (same cell-building rule as the CLI)."""
    cells: dict[str, dict[str, float]] = {}
    n_per_cell: int | None = None
    for r in rows:
        if r.get("status") != "ok" or not r.get("overall"):
            continue
        n = int(r["overall"].get("n", 0) or 0)
        if n_per_cell is None:
            n_per_cell = n
        elif n != n_per_cell:
            return None  # mixed-n matrices are not pooled silently
        cells.setdefault(r["model_id"], {})[
            f"{r['factor']}={r['factor_level']}"
        ] = float(r["overall"]["accuracy"])
    configs = sorted({c for m in cells.values() for c in m})
    matrix, names = [], []
    for model, cfgs in cells.items():
        if len(cfgs) < 2:
            continue
        names.append(model)
        matrix.append([cfgs.get(c) for c in configs])
    if len(names) < 2 or not n_per_cell:
        return None
    out = evaluation_reliability_score(matrix, n_per_cell=n_per_cell,
                                       n_boot=n_boot, seed=seed)
    out["models"] = names
    out["n_configs_used"] = len(configs)
    out["n_missing_cells"] = sum(1 for row in matrix for v in row if v is None)
    out["excluded_models_lt2_cells"] = sorted(set(cells) - set(names))
    out["provenance"] = "DERIVED from measured registry rows; not a new measurement"
    return out


def build_dashboard(
    registry_path: Path,
    repo_root: Path,
    *,
    failure_runs: list[Path] | None = None,
    n_boot: int = 300,
    seed: int = 0,
) -> dict[str, Any]:
    rows = load_registry(registry_path)

    # coverage: statuses need blobs; load each row's artifact once
    blobs: dict[int, dict[str, Any] | None] = {}
    for i, r in enumerate(rows):
        p = r.get("path")
        fp = Path(p) if p and Path(p).is_absolute() else repo_root / (p or "")
        blobs[i] = json.loads(fp.read_text(encoding="utf-8")) if fp.exists() else None
    status_counts = {MEASURED: 0, SAMPLED: 0, PENDING: 0}
    for i, r in enumerate(rows):
        status_counts[classify_row(r, blobs[i])] += 1

    # models: measured cells only
    models: dict[str, dict[str, Any]] = {}
    for r in rows:
        if r.get("status") != "ok" or not r.get("overall"):
            continue
        acc = r["overall"].get("accuracy")
        m = models.setdefault(r["model_id"], {"n_cells": 0, "accuracies": []})
        m["n_cells"] += 1
        if acc is not None:
            m["accuracies"].append(float(acc))
    model_summary = {}
    for name, m in sorted(models.items()):
        accs = m.pop("accuracies")
        model_summary[name] = {
            "n_cells": m["n_cells"],
            "mean_accuracy": round(sum(accs) / len(accs), 4) if accs else None,
            "min_accuracy": min(accs) if accs else None,
            "max_accuracy": max(accs) if accs else None,
        }

    # deviations: verify every row whose artifact exists (fail closed)
    verifications = []
    n_pass = n_fail = 0
    for i, r in enumerate(rows):
        if blobs[i] is None:
            n_fail += 1
            continue
        ver = verify_reproduction(r, repo_root)
        verifications.append(ver)
        n_pass += ver["all_match"] is True
        n_fail += ver["all_match"] is not True

    # failures: optional, only for explicitly listed runs
    failure_reports = {}
    if failure_runs:
        from apertus_eval_prep.failures import failure_taxonomy
        for fp in failure_runs:
            blob = json.loads(Path(fp).read_text(encoding="utf-8"))
            failure_reports[Path(fp).stem] = failure_taxonomy(blob)

    return {
        "registry": str(registry_path),
        "n_rows": len(rows),
        "coverage": status_counts,
        "models": model_summary,
        "ers": _ers_section(rows, n_boot=n_boot, seed=seed),
        "deviations": {
            "n_verified": len(verifications),
            "n_pass": n_pass,
            "n_fail": n_fail,
            "n_pending_no_artifact": status_counts[PENDING],
            "details_fail": [
                {"run_id": v["run_id"],
                 "failed": [c["name"] for c in v["checks"] if c["match"] is not True]}
                for v in verifications if not v["all_match"]
            ],
            "note": "fail closed: rows without artifacts count as failures",
        },
        "failures": failure_reports,
        "provenance": "dashboard DERIVED from committed registry + artifacts",
    }


def render_dashboard_markdown(d: dict[str, Any]) -> str:
    lines = [
        "# Research dashboard",
        "",
        f"Registry: `{d['registry']}` — {d['n_rows']} rows "
        f"(MEASURED {d['coverage'][MEASURED]}, SAMPLED {d['coverage'][SAMPLED]}, "
        f"PENDING {d['coverage'][PENDING]}).",
        "",
        "## Models (measured cells only)",
        "",
        "| model | cells | mean acc | min | max |",
        "|---|---|---|---|---|",
    ]
    for name, m in d["models"].items():
        lines.append(
            f"| {name} | {m['n_cells']} | {m['mean_accuracy']} | "
            f"{m['min_accuracy']} | {m['max_accuracy']} |"
        )
    ers = d["ers"]
    lines += ["", "## Evaluation Reliability Score (DERIVED, provisional)", ""]
    if ers is None:
        lines.append("_Not computable (needs >=2 models x >=2 shared cells "
                     "with uniform n) — reported, not imputed._")
    else:
        comps = ", ".join(
            f"{k}={v:.3f}" if v is not None else f"{k}=None"
            for k, v in ers["components"].items()
        )
        lines += [
            f"- **ERS: {ers['ers']}** ({ers['n_components']} components)",
            f"- components: {comps}",
            f"- bootstrap tau={ers['bootstrap']['mean_tau']}, "
            f"p(reversal)={ers['bootstrap']['p_any_reversal']}",
            f"- missing cells skipped: {ers['n_missing_cells']}",
        ]
    dev = d["deviations"]
    lines += [
        "", "## Artifact verification (deviation checks)", "",
        f"- pass: **{dev['n_pass']}** / fail: **{dev['n_fail']}** "
        f"(pending/no artifact: {dev['n_pending_no_artifact']})",
    ]
    for f in dev["details_fail"]:
        lines.append(f"- FAIL `{f['run_id']}`: {', '.join(f['failed']) or 'unknown'}")
    if d["failures"]:
        lines += ["", "## Failure taxonomy (listed runs)", ""]
        for name, fr in d["failures"].items():
            lines.append(f"- **{name}**: {fr['total']} items, "
                         f"failure rate {fr['failure_rate']}")
    lines.append("")
    return "\n".join(lines) + "\n"