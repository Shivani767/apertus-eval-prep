"""Frontend data export: one compact `site.json` from committed research artifacts.

Architecture (single source of truth, no second dataset):

    results/registry_paper.jsonl  +  results/runs/*.json
              |                            |
              +---------- site.py ---------+--> site.json --> frontend

Everything emitted here is recomputed from the committed artifacts on every
run: nothing is hand-copied into the frontend and nothing is fabricated.

Provenance labels used throughout:
  MEASURED  — read directly from a run artifact (items, latency, hardware).
  DERIVED   — computed from measured data (rankings, deltas, statistics).
  PENDING   — registry row whose artifact is absent (reported, never zeroed).

Statistics reuse the existing engine (`stats.py`) — paired bootstrap CI, sign-flip
permutation test, McNemar, Cohen's h, Holm-Bonferroni and Benjamini-Hochberg —
so the numbers on the site are the same numbers the paper pipeline produces.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from apertus_eval_prep.failures import failure_taxonomy
from apertus_eval_prep.pareto import pareto_front
from apertus_eval_prep.registry import load_registry
from apertus_eval_prep.reliability import ers_ablation, evaluation_reliability_score
from apertus_eval_prep.reproduce import reproduction_plan, verify_reproduction
from apertus_eval_prep.result_schema import MEASURED, PENDING, SAMPLED, classify_row
from apertus_eval_prep.stability import cohens_h
from apertus_eval_prep.stats import (
    benjamini_hochberg,
    bootstrap_paired_diff_ci,
    holm_bonferroni,
    item_correctness,
    mcnemar,
    pairwise_reversals,
    permutation_paired_test,
    rank_high_is_better,
)

SCHEMA_VERSION = 1
ND = 5  # decimals kept in the export


def _r(x: float | None, nd: int = ND) -> float | None:
    return None if x is None else round(float(x), nd)


def _blob_path(row: dict[str, Any], repo_root: Path) -> Path:
    p = row.get("path")
    return Path(p) if p and Path(p).is_absolute() else repo_root / (p or "")


def _short(model_id: str) -> str:
    """Compact display label: 'Qwen/Qwen2.5-3B-Instruct' -> 'Qwen2.5-3B-Instruct'."""
    return model_id.split("/")[-1]


def config_key(factor: str, factor_level: str) -> str:
    return f"{factor}={factor_level}"


def cell_from_row(
    row: dict[str, Any], blob: dict[str, Any] | None, repo_root: Path
) -> dict[str, Any]:
    """One registry row -> one UI cell. MEASURED fields from the artifact only."""
    settings = (blob or {}).get("manifest", {}).get("settings", {}) or {}
    hardware = (blob or {}).get("manifest", {}).get("hardware", {}) or {}
    overall = row.get("overall") or {}
    tasks = (blob or {}).get("tasks") or {}
    status = classify_row(row, blob)
    key = config_key(row.get("factor", "control"), row.get("factor_level", "control"))
    factor = row.get("factor", "control")
    level = row.get("factor_level", "control")

    axes = {
        "prompt_id": settings.get("prompt_id"),
        "fewshot": bool(settings.get("fewshot_path")),
        "chat_template": settings.get("chat_template"),
        "system_prompt": settings.get("system_prompt"),
        "backend": settings.get("backend"),
        "quantization": settings.get("quantization") or "none",
        "dtype": settings.get("dtype"),
        "temperature": settings.get("temperature"),
        "top_p": settings.get("top_p"),
        "seed": settings.get("seed"),
        "max_new_tokens": settings.get("max_new_tokens"),
        "device": settings.get("device"),
        "gpu": hardware.get("gpu"),
    }
    return {
        "run_id": row.get("run_id"),
        "model_id": row.get("model_id"),
        "model_label": _short(row.get("model_id") or ""),
        "factor": factor,
        "factor_level": level,
        "config_key": key,
        "config_hash": row.get("config_hash"),
        "experiment_id": row.get("experiment_id"),
        "status": status,
        "provenance": "MEASURED" if status in (MEASURED, SAMPLED) else "PENDING",
        "n": overall.get("n"),
        "correct": overall.get("correct"),
        "accuracy": _r(overall.get("accuracy")),
        "accuracy_ci95": [_r(v) for v in (overall.get("accuracy_ci95") or [])] or None,
        "axes": axes,
        "tasks": {
            t: {
                "n": v.get("n"),
                "correct": v.get("correct"),
                "accuracy": _r(v.get("accuracy")),
                "ci95": [_r(x) for x in (v.get("accuracy_ci95") or [])] or None,
            }
            for t, v in tasks.items()
            if t != "overall"
        },
        "latency": (blob or {}).get("latency"),
        "git_commit": row.get("git_commit"),
        "utc": row.get("utc"),
        "path": row.get("path"),
    }


def _measured(cells: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in cells if c.get("accuracy") is not None]


def _items_by_id(blob: dict[str, Any] | None) -> dict[str, bool]:
    if not blob:
        return {}
    return item_correctness(blob.get("items") or [])


def build_statistics(
    cells: Sequence[dict[str, Any]],
    blobs: dict[str, dict[str, Any]],
    *,
    base_key: str = "control=control",
    n_boot: int = 500,
    n_perm: int = 2000,
    seed: int = 0,
) -> dict[str, Any]:
    """Paired statistical evidence for every control-vs-variant cell pair.

    Reuses the engine in `stats.py`: paired bootstrap CI of the accuracy
    difference, sign-flip permutation test, McNemar, Cohen's h. Adjusted
    p-values come from Holm-Bonferroni (FWER) and Benjamini-Hochberg (FDR)
    applied across ALL comparisons in the returned set. Item ids present in
    only one run are dropped and counted (n_dropped), never filled.
    """
    meas = {c["config_key"]: c for c in _measured(cells)}
    base = meas.get(base_key)
    comparisons: list[dict[str, Any]] = []
    if base is not None:
        b_by_model = {c["model_id"]: c for c in _measured(cells)
                      if c["config_key"] == base_key}
        for key in sorted(meas):
            if key == base_key:
                continue
            var_cell = meas[key]
            b_cell = b_by_model.get(var_cell["model_id"])
            if b_cell is None:
                continue
            b_all = _items_by_id(blobs.get(b_cell["run_id"] or ""))
            v_all = _items_by_id(blobs.get(var_cell["run_id"] or ""))
            ids = sorted(set(b_all) & set(v_all))
            if not b_all or not v_all or not ids:
                continue
            boot = bootstrap_paired_diff_ci(b_all, v_all, n_boot=n_boot, seed=seed)
            perm = permutation_paired_test(b_all, v_all, n_perm=n_perm, seed=seed)
            mc = mcnemar([b_all[i] for i in ids], [v_all[i] for i in ids])
            comparisons.append(
                {
                    "model_id": var_cell["model_id"],
                    "model_label": var_cell["model_label"],
                    "base_key": base_key,
                    "variant_key": key,
                    "factor": var_cell["factor"],
                    "factor_level": var_cell["factor_level"],
                    "n_paired": boot["n_paired"],
                    "n_dropped": boot["n_dropped"],
                    "base_accuracy": _r(b_cell["accuracy"]),
                    "variant_accuracy": _r(var_cell["accuracy"]),
                    "delta": _r(boot["delta_mean"]),
                    "delta_ci95": [_r(boot["lo"]), _r(boot["hi"])],
                    "ci_excludes_zero": (
                        boot["lo"] is not None
                        and (boot["lo"] > 0 or boot["hi"] < 0)
                    ),
                    "perm_p": _r(perm["p_value"], 6),
                    "mcnemar": {k: mc[k] for k in
                                ("a_correct_b_wrong", "a_wrong_b_correct",
                                 "disagreement_rate", "chi2", "p_value")},
                    "cohens_h": _r(cohens_h(b_cell["accuracy"],
                                            var_cell["accuracy"])),
                    "provenance": "DERIVED from MEASURED per-item correctness",
                }
            )
    ps = [c["perm_p"] for c in comparisons if c["perm_p"] is not None]
    if ps:
        holm = holm_bonferroni(ps)
        bh = benjamini_hochberg(ps)
        k = 0
        for c in comparisons:
            if c["perm_p"] is not None:
                c["perm_p_holm"] = _r(holm[k], 6)
                c["perm_p_bh"] = _r(bh[k], 6)
                k += 1
            else:
                c["perm_p_holm"] = None
                c["perm_p_bh"] = None
    return {
        "base_key": base_key,
        "n_comparisons": len(comparisons),
        "n_tests_corrected": len(ps),
        "n_boot": n_boot,
        "n_perm": n_perm,
        "seed": seed,
        "comparisons": comparisons,
        "methods": [
            "paired percentile bootstrap (joint item resampling)",
            "sign-flip permutation test (Monte-Carlo, seeded)",
            "McNemar continuity-corrected chi2",
            "Cohen's h effect size",
            "Holm-Bonferroni FWER adjustment",
            "Benjamini-Hochberg FDR adjustment",
        ],
        "provenance": "DERIVED",
    }


def build_failures(
    cells: Sequence[dict[str, Any]], blobs: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Per-cell failure taxonomy (measured counts from run artifacts)."""
    out = []
    for c in _measured(cells):
        blob = blobs.get(c["run_id"] or "")
        tax = failure_taxonomy(blob or {})
        out.append(
            {
                "run_id": c["run_id"],
                "model_id": c["model_id"],
                "model_label": c["model_label"],
                "config_key": c["config_key"],
                "total": tax["total"],
                "counts": {k: _r(v, 0) for k, v in tax["counts"].items()},
                "rates": {k: _r(v) for k, v in tax["rates"].items()},
                "failure_rate": _r(tax["failure_rate"]),
                "per_task": tax["per_task"],
                "artifact_present": bool(blob),
                "provenance": "MEASURED per-item counts",
            }
        )
    return out


def build_reliability(cells: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """ERS over shared configs + seed arm, computed from cell accuracies.

    Only models with >= 2 non-sampled configs enter the config matrix (a
    within-model spread over < 2 configs is undefined). Models with fewer
    are listed in `excluded_models` so the UI can say so explicitly.
    """
    meas = _measured(cells)
    # Per-model "seed scores": the sampled T=0.7 arm, since sampled rows are
    # run at temperature and tagged SAMPLED (labels preserved by classify_row).
    nonsampled = {m: [c for c in meas if c["model_id"] == m and c["factor"] != "sampled"]
                  for m in sorted({c["model_id"] for c in meas})}
    models = [m for m, cs in nonsampled.items() if len(cs) >= 2]
    excluded = sorted(set(nonsampled) - set(models))
    seed_row = {m: [c for c in meas if c["model_id"] == m and c["factor"] == "sampled"]
                for m in models}
    seed_scores = [[c["accuracy"] for c in seed_row[m]] for m in models]
    # Config matrix: one column per non-sampled measured config.
    configs = sorted({c["config_key"] for c in meas if c["factor"] != "sampled"})
    matrix = [[next((c["accuracy"] for c in meas
                     if c["model_id"] == m and c["config_key"] == k), None)
               for k in configs] for m in models]
    ns = [c["n"] for c in meas if c["n"]]
    n_common = max(set(ns), key=ns.count) if ns else None
    ers = evaluation_reliability_score(matrix, n_per_cell=n_common,
                                       seed_scores=seed_scores if all(seed_scores) else None,
                                       n_boot=300, seed=0)
    abl = ers_ablation(matrix, n_per_cell=n_common,
                       seed_scores=seed_scores if all(seed_scores) else None,
                       n_boot=300, seed=0)
    ers["ablation"] = abl["drop_one"]
    ers["models"] = models
    ers["excluded_models"] = excluded
    ers["n_configs_in_matrix"] = len(configs)
    ers["skipped_configs"] = sorted(
        {c["config_key"] for c in meas if c["factor"] == "sampled"})
    ers["disclaimer"] = (
        "PROVISIONAL research diagnostic. Descriptive summary of how much "
        "model rankings can be trusted under the measured configs — not a "
        "validated universal benchmark reliability metric. See the components, "
        "not just the headline number."
    )
    return ers


def build_reproducibility(
    rows: Sequence[dict[str, Any]], repo_root: Path
) -> dict[str, Any]:
    """Reproduction validation: artifact verification + commands (MEASURED)."""
    import subprocess

    try:
        commit = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception:
        commit = None
    results = [verify_reproduction(dict(r), repo_root) for r in rows]
    n_pass = sum(1 for v in results if v["all_match"])
    summary = [{"run_id": v["run_id"], "config_hash": v["config_hash"],
                "all_match": v["all_match"],
                "failed": [c["name"] for c in v["checks"] if c["match"] is not True]}
               for v in results]
    detail = {v["run_id"]: v for v in results}
    plans = {r.get("run_id"): reproduction_plan(dict(r), repo_root) for r in rows}
    commands = {
        rid: {"sweep_command": p.get("sweep_command"),
              "eval_command_hint": p.get("eval_command_hint")}
        for rid, p in plans.items()
    }
    return {
        "git_commit": commit,
        "n_verified": len(results),
        "n_pass": n_pass,
        "n_fail": len(results) - n_pass,
        "rows": summary,
        "detail": detail,
        "commands": commands,
        "provenance": "MEASURED cross-checks of committed artifacts vs registry",
    }


def build_pareto(
    cells: Sequence[dict[str, Any]], blobs: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Cost-vs-quality Pareto: latency (ms, lower better) vs accuracy.

    Cells whose artifact records no positive e2e_ms_mean are EXCLUDED as
    unavailable (the vLLM placeholder 0.0 is never treated as zero cost).
    """
    points = []
    for c in _measured(cells):
        lat = (blobs.get(c["run_id"] or "") or {}).get("latency") or {}
        e2e = lat.get("e2e_ms_mean")
        points.append({
            "label": f"{c['model_label']} / {c['config_key']}",
            "model_id": c["model_id"],
            "model_label": c["model_label"],
            "config_key": c["config_key"],
            "latency_ms": _r(e2e) if e2e else None,
            "accuracy": c["accuracy"],
            "tts": _r(lat.get("tokens_per_sec_mean")),
        })
    res = pareto_front(points, x_key="latency_ms", y_key="accuracy")
    res["provenance"] = (
        "MEASURED cell accuracies; latency from artifact latency blocks; "
        "UNAVAILABLE-latency cells excluded"
    )
    return res


def build_site(
    repo_root: Path,
    registry_path: Path,
    *,
    n_boot: int = 500,
    n_perm: int = 2000,
    seed: int = 0,
) -> dict[str, Any]:
    """Assemble the full frontend export from committed artifacts (no blobs kept)."""
    rows = load_registry(registry_path)
    blobs: dict[str, dict[str, Any]] = {}
    cells = []
    for row in rows:
        p = _blob_path(row, repo_root)
        blob = None
        if p.exists():
            blob = json.loads(p.read_text(encoding="utf-8"))
            blobs[row.get("run_id") or ""] = blob
        cells.append(cell_from_row(row, blob, repo_root))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "registry": str(registry_path.relative_to(repo_root))
        if registry_path.is_absolute() else str(registry_path),
        "coverage": build_coverage(cells, rows, repo_root),
        "models": build_models(cells),
        "configs": build_configs(cells),
        "cells": cells,
        "rankings": build_rankings(cells),
        "ranking_comparisons": build_ranking_comparisons(build_rankings(cells)),
        "statistics": build_statistics(cells, blobs, n_boot=n_boot,
                                       n_perm=n_perm, seed=seed),
        "reliability": build_reliability(cells),
        "failures": build_failures(cells, blobs),
        "pareto": build_pareto(cells, blobs),
        "reproducibility": build_reproducibility(rows, repo_root),
        "provenance_legend": {
            "MEASURED": "read directly from a committed run artifact",
            "SAMPLED": "measured with temperature sampling (labels preserved)",
            "DERIVED": "computed from measured data by a documented function",
            "PENDING": "registry row without artifact — shown, never zero-filled",
        },
    }


def write_site(site: dict[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "site.json"
    path.write_text(json.dumps(site, indent=1, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def build_rankings(cells: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """One ranking per configuration over the models measured in it (DERIVED)."""
    by_config: dict[str, list[dict[str, Any]]] = {}
    for c in _measured(cells):
        by_config.setdefault(c["config_key"], []).append(c)
    out = []
    for key in sorted(by_config):
        group = sorted(by_config[key], key=lambda c: c["model_id"])
        scores = [c["accuracy"] for c in group]
        ranks = rank_high_is_better(scores)
        members = [
            {
                "model_id": c["model_id"],
                "model_label": c["model_label"],
                "score": c["accuracy"],
                "rank": ranks[i],
                "n": c["n"],
                "ci95": c["accuracy_ci95"],
                "run_id": c["run_id"],
                "factor": c["factor"],
                "factor_level": c["factor_level"],
            }
            for i, c in enumerate(group)
        ]
        members_sorted = sorted(members, key=lambda m: (m["rank"], m["model_label"]))
        out.append(
            {
                "config_key": key,
                "factor": group[0]["factor"],
                "factor_level": group[0]["factor_level"],
                "n_models": len(members),
                "ranking": members_sorted,
                "ranks": [m["rank"] for m in sorted(members, key=lambda m: m["model_id"])],
                "models": sorted(m["model_id"] for m in members),
                "provenance": "DERIVED from measured cell accuracies",
            }
        )
    return out


def build_ranking_comparisons(
    rankings: Sequence[dict[str, Any]], *, base_key: str = "control=control"
) -> list[dict[str, Any]]:
    """Control vs every other configuration, on their shared models (DERIVED).

    Reports per-model score delta and rank movement, Kendall tau between the
    two rank vectors, and whether the ordering changed at all (`reordered`).
    """
    by_key = {r["config_key"]: r for r in rankings}
    base = by_key.get(base_key)
    if base is None:
        return []
    out = []
    for key in sorted(by_key):
        if key == base_key:
            continue
        var = by_key[key]
        shared = sorted(set(base["models"]) & set(var["models"]))
        if len(shared) < 2:
            continue
        b_by, v_by = (
            {m["model_id"]: m for m in base["ranking"]},
            {m["model_id"]: m for m in var["ranking"]},
        )
        base_ranks = [b_by[m]["rank"] for m in shared]
        var_ranks = [v_by[m]["rank"] for m in shared]
        members = [
            {
                "model_id": m,
                "model_label": b_by[m]["model_label"],
                "base_score": b_by[m]["score"],
                "variant_score": v_by[m]["score"],
                "delta": _r(v_by[m]["score"] - b_by[m]["score"]),
                "base_rank": b_by[m]["rank"],
                "variant_rank": v_by[m]["rank"],
                "rank_move": v_by[m]["rank"] - b_by[m]["rank"],
                "ci95": v_by[m]["ci95"],
            }
            for m in shared
        ]
        from apertus_eval_prep.stats import kendall_tau_b

        tau = kendall_tau_b(base_ranks, var_ranks)
        flips = pairwise_reversals(base_ranks, var_ranks)
        base_order = [m for m in shared]
        base_order.sort(key=lambda m: b_by[m]["rank"])
        variant_order = sorted(shared, key=lambda m: v_by[m]["rank"])
        out.append(
            {
                "base_key": base_key,
                "variant_key": key,
                "factor": var["factor"],
                "factor_level": var["factor_level"],
                "n_shared_models": len(shared),
                "excluded_from_base": sorted(set(base["models"]) - set(shared)),
                "members": members,
                "base_order": [b_by[m]["model_label"] for m in base_order],
                "variant_order": [v_by[m]["model_label"] for m in variant_order],
                "tau": _r(tau),
                "n_reversals": flips,
                "reordered": flips > 0,
                "provenance": "DERIVED from measured cell accuracies",
            }
        )
    return out


def build_coverage(
    cells: Sequence[dict[str, Any]], rows: Sequence[dict[str, Any]], repo_root: Path
) -> dict[str, Any]:
    """Coverage counts. planned_cells is recomputed from the OFAT study YAML."""
    planned = None
    study_path = repo_root / "configs/experiments/stability.yaml"
    if study_path.exists():
        from apertus_eval_prep.sweep import expand_ofat, load_study

        planned = len(expand_ofat(load_study(study_path), profile="t4"))
    statuses = [c["status"] for c in cells]
    measured = sum(1 for s in statuses if s in (MEASURED, SAMPLED))
    pending = sum(1 for s in statuses if s == PENDING)
    factors = sorted({c["factor"] for c in cells})
    return {
        "n_rows": len(rows),
        "n_cells": len(cells),
        "measured": measured,
        "sampled": sum(1 for s in statuses if s == SAMPLED),
        "pending": pending,
        "planned_cells": planned,
        "completion": _r(measured / planned) if planned else None,
        "n_models": len({c["model_id"] for c in cells}),
        "n_configs": len({c["config_key"] for c in cells}),
        "n_factors": len(factors),
        "factors": factors,
        "provenance": "planned_cells DERIVED from configs/experiments/stability.yaml (t4); "
                      "counts MEASURED from registry",
    }


def build_models(cells: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for model_id in sorted({c["model_id"] for c in _measured(cells)}):
        group = [c for c in _measured(cells) if c["model_id"] == model_id]
        accs = [c["accuracy"] for c in group]
        out.append(
            {
                "model_id": model_id,
                "label": _short(model_id),
                "n_cells": len(group),
                "mean_accuracy": _r(sum(accs) / len(accs)),
                "min_accuracy": _r(min(accs)),
                "max_accuracy": _r(max(accs)),
                "spread": _r(max(accs) - min(accs)),
                "provenance": "DERIVED from measured cell accuracies",
            }
        )
    return out


def build_configs(cells: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for key in sorted({c["config_key"] for c in cells}):
        group = [c for c in cells if c["config_key"] == key]
        meas = _measured(group)
        out.append(
            {
                "config_key": key,
                "factor": group[0]["factor"],
                "factor_level": group[0]["factor_level"],
                "n_models": len(meas),
                "n_pending": len(group) - len(meas),
                "models": sorted(c["model_id"] for c in meas),
                "provenance": "DERIVED from registry rows",
            }
        )
    return out

