"""Compute every number used in the paper from committed measurement artifacts.

Outputs ``paper/analysis/statistics.json`` — the single source of truth that
``generate_tables.py``, ``generate_figures.py``, and ``validate_paper.py``
all read. No numbers in the paper may come from anywhere else.

All statistical routines are imported from the repository's own engine
(``apertus_eval_prep.stats`` / ``ranking`` / ``reliability`` / ``stability`` /
``failures``) so the paper reports exactly what the codebase computes:
Wilson score intervals, continuity-corrected McNemar, Kendall tau-b,
Holm-Bonferroni / Benjamini-Hochberg adjustments, Cohen's h, seeded bootstrap
ranking stability, and the provisional Evaluation Reliability Score.

Analyses produced here
----------------------
1. registry_verification : per-row artifact cross-checks.
2. control               : control accuracies + Wilson CIs, per task.
3. contrasts             : every OFAT level vs same-model control, paired by
                           item id: delta, McNemar (raw + Holm + BH over the
                           full contrast family), Cohen's h.
4. factor_sensitivity    : max |delta| per factor per model (OFAT-safe).
5. ranking               : 8-config complete matrix for the three full models;
                           competition ranks, Kendall tau-b vs control
                           ordering, reversals, pairwise win rates, CI
                           overlap per pair/config, bootstrap rank stability.
6. sampling              : T=0.7 seed spread + greedy-seed invariance.
7. latency               : measured HF latency blocks; vLLM placeholders
                           reported as UNAVAILABLE (never zero-filled).
8. failures              : mutually exclusive failure taxonomy per cell.
9. ers                   : provisional Evaluation Reliability Score recompute.
10. provenance           : git commits, UTC window, matrix coverage vs plan.

Run:  python3 scripts/statistical_analysis.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from statistics import mean, pstdev

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "src"))

from paper_common import (  # noqa: E402
    MODELS_IN_MATRIX,
    REPO_ROOT,
    SHORT_MODEL,
    SHARED_CONFIGS,
    load_paper_data,
)

from apertus_eval_prep.failures import CATEGORIES, classify_item  # noqa: E402
from apertus_eval_prep.ranking import (  # noqa: E402
    bootstrap_ranking_stability,
    pairwise_win_rates,
    rank_distributions,
)
from apertus_eval_prep.reliability import evaluation_reliability_score  # noqa: E402
from apertus_eval_prep.stats import (  # noqa: E402
    benjamini_hochberg,
    chi2_sf_1df,
    cis_overlap,
    holm_bonferroni,
    kendall_tau_b,
    mcnemar,
    pairwise_reversals,
    rank_high_is_better,
    wilson_interval,
)
from apertus_eval_prep.stability import (  # noqa: E402
    bootstrap_ci_mean,
    coef_of_variation,
    score_range,
    score_std,
)

OUT_DIR = REPO / "paper" / "analysis"
TASKS = ["arc_easy", "gsm8k", "hellaswag", "mgsm"]


def pp(x: float | None) -> float | None:
    """fraction -> percentage points, rounded to 2 decimals."""
    return None if x is None else round(100.0 * x, 2)


def main() -> int:
    data = load_paper_data()
    if data["problems"]:
        print("INTEGRITY PROBLEMS:", *data["problems"], sep="\n  ")
        return 1
    cells = data["cells"]
    rows = data["rows"]

    out: dict = {"registry_verification": data["verifications"]}

    # ------------------------------------------------------------------ control
    control = {}
    for m in MODELS_IN_MATRIX:
        c = cells[(m, "control", "control")]
        overall = c["overall"]
        per_task = {t: c["tasks"][t] for t in TASKS}
        control[SHORT_MODEL[m]] = {
            "run_id": c["run_id"],
            "config_hash": c["config_hash"],
            "n": overall["n"],
            "correct": overall["correct"],
            "accuracy": overall["accuracy"],
            "ci95": overall["accuracy_ci95"],
            "tasks": per_task,
            "git_commit": c["git_commit"],
            "utc": c["utc"],
        }
    out["control"] = control

    # ---------------------------------------------------------------- contrasts
    # Family: every non-control measured level of every factor vs its
    # same-model control, paired by item id. Greedy-seed contrasts are part of
    # the family (they measure decoding determinism, not stochasticity).
    contrasts = []
    for m in MODELS_IN_MATRIX:
        short = SHORT_MODEL[m]
        ctrl = cells[(m, "control", "control")]
        a_by_id = ctrl["correct_by_id"]
        p_ctrl = ctrl["overall"]["accuracy"]
        for key, c in sorted(cells.items()):
            mm, factor, level = key
            if mm != m or factor == "control":
                continue
            b_by_id = c["correct_by_id"]
            shared = sorted(set(a_by_id) & set(b_by_id))
            dropped = len((set(a_by_id) | set(b_by_id)) - set(shared))
            mc = mcnemar([a_by_id[i] for i in shared], [b_by_id[i] for i in shared])
            p_b = c["overall"]["accuracy"]
            contrasts.append(
                {
                    "model": short,
                    "model_id": m,
                    "factor": factor,
                    "level": level,
                    "run_id": c["run_id"],
                    "config_hash": c["config_hash"],
                    "n": c["overall"]["n"],
                    "n_paired": len(shared),
                    "n_dropped": dropped,
                    "acc_control": p_ctrl,
                    "acc_variant": p_b,
                    "delta_pp": pp(p_b - p_ctrl),
                    "cohens_h": round(
                        2 * math.asin(math.sqrt(p_b))
                        - 2 * math.asin(math.sqrt(p_ctrl)),
                        4,
                    ),
                    "mcnemar": mc,
                }
            )
    # Multiple-comparison adjustments must use unrounded p-values: recompute
    # each McNemar p from the exact discordant counts (the stored "p_value"
    # field is rounded to 6 decimals for display only).
    def _raw_p(mc: dict) -> float:
        b, c_ = mc["a_correct_b_wrong"], mc["a_wrong_b_correct"]
        disc = b + c_
        if disc == 0:
            return 1.0
        return chi2_sf_1df(max(0, abs(b - c_) - 1) ** 2 / disc)

    raw_ps = [_raw_p(c["mcnemar"]) for c in contrasts]
    holm = holm_bonferroni(raw_ps)
    bh = benjamini_hochberg(raw_ps)
    for c, h, b, raw in zip(contrasts, holm, bh, raw_ps):
        c['mcnemar']['p_value'] = raw
        c["p_holm"] = h
        c["p_bh"] = b
    out["contrasts"] = contrasts

    # ------------------------------------------------------- factor sensitivity
    sens = {}
    for m in MODELS_IN_MATRIX:
        short = SHORT_MODEL[m]
        by_factor: dict[str, list[float]] = {}
        for (mm, factor, level), c in sorted(cells.items()):
            if mm != m:
                continue
            by_factor.setdefault(factor, []).append(c["overall"]["accuracy"])
        sens[short] = {}
        for factor, vals in sorted(by_factor.items()):
            sens[short][factor] = {
                "n_configs": len(vals),
                "range_pp": pp(score_range(vals)),
                "std_pp": pp(score_std(vals)),
                "cv": round(coef_of_variation(vals), 4)
                if coef_of_variation(vals) is not None
                else None,
            }
    # max |delta vs control| per factor (OFAT-safe summary)
    for m in MODELS_IN_MATRIX:
        short = SHORT_MODEL[m]
        for factor in {c["factor"] for c in contrasts if c["model"] == short}:
            deltas = [
                abs(c["delta_pp"])
                for c in contrasts
                if c["model"] == short and c["factor"] == factor
            ]
            sens[short][factor]["max_abs_delta_pp"] = (
                round(max(deltas), 2) if deltas else None
            )
    out["factor_sensitivity"] = sens


    # ----------------------------------------------------------------- ranking
    # Complete 8-config matrix over the three full models.
    matrix: list[list[float | None]] = []
    for m in MODELS_IN_MATRIX:
        row = []
        for factor, level in SHARED_CONFIGS:
            c = cells.get((m, factor, level))
            row.append(c["overall"]["accuracy"] if c else None)
        matrix.append(row)
    config_labels = [f"{f}={l}" for f, l in SHARED_CONFIGS]
    config_labels[0] = "control"
    out["ranking"] = {
        "config_labels": config_labels,
        "models": [SHORT_MODEL[m] for m in MODELS_IN_MATRIX],
        "matrix": matrix,
        "cells": [
            {
                "config": config_labels[ci],
                "model": SHORT_MODEL[m],
                "acc": cells[(m, f, l)]["overall"]["accuracy"],
                "ci95": cells[(m, f, l)]["overall"]["accuracy_ci95"],
                "correct": cells[(m, f, l)]["overall"]["correct"],
                "n": cells[(m, f, l)]["overall"]["n"],
                "tasks": {
                    t: cells[(m, f, l)]["tasks"][t] for t in TASKS
                },
            }
            for ci, (f, l) in enumerate(SHARED_CONFIGS)
            for m in MODELS_IN_MATRIX
            if (m, f, l) in cells
        ],
    }

    control_order = rank_high_is_better([r[0] for r in matrix])
    tau_rows = []
    for ci, (factor, level) in enumerate(SHARED_CONFIGS):
        col = [matrix[mi][ci] for mi in range(len(MODELS_IN_MATRIX))]
        if any(v is None for v in col):
            tau_rows.append(
                {"config": config_labels[ci], "tau_b": None, "reversals": None,
                 "n_models": 3, "measured": False}
            )
            continue
        variant_ranks = rank_high_is_better(col)
        tau = kendall_tau_b(control_order, variant_ranks)
        tau_rows.append(
            {
                "config": config_labels[ci],
                "tau_b": round(tau, 4) if tau is not None else None,
                "reversals": pairwise_reversals(control_order, variant_ranks),
                "ranks": variant_ranks,
                "accs": [round(v, 4) for v in col],
                "n_models": 3,
                "measured": True,
            }
        )
    out["ranking"]["tau_vs_control"] = tau_rows

    # CI overlap per model pair per config (interval-aware comparisons)
    ci_matrix = {}
    for m in MODELS_IN_MATRIX:
        for factor, level in SHARED_CONFIGS:
            c = cells.get((m, factor, level))
            if c:
                ci_matrix[(m, factor, level)] = c["overall"]["accuracy_ci95"]
    pair_overlap = {}
    for i, m1 in enumerate(MODELS_IN_MATRIX):
        for j, m2 in enumerate(MODELS_IN_MATRIX):
            if j <= i:
                continue
            overlaps = []
            for factor, level in SHARED_CONFIGS:
                a = ci_matrix.get((m1, factor, level))
                b = ci_matrix.get((m2, factor, level))
                if a is None or b is None:
                    overlaps.append(None)
                else:
                    overlaps.append(bool(cis_overlap(a, b)))
            pair_overlap[f"{SHORT_MODEL[m1]} vs {SHORT_MODEL[m2]}"] = overlaps
    out["ranking"]["pair_ci_overlap"] = pair_overlap

    win = pairwise_win_rates(matrix)
    out["ranking"]["pairwise_win_rates"] = {
        f"{SHORT_MODEL[MODELS_IN_MATRIX[i]]} > {SHORT_MODEL[MODELS_IN_MATRIX[j]]}": win[i][j]
        for i in range(3)
        for j in range(3)
        if i != j
    }
    out["ranking"]["rank_distributions"] = rank_distributions(matrix)
    bs = bootstrap_ranking_stability(matrix, n_boot=2000, seed=0)
    out["ranking"]["bootstrap"] = bs

    # Phi vs Qwen-3B head-to-head detail (the reversal)
    h2h = []
    for ci, (factor, level) in enumerate(SHARED_CONFIGS):
        a = cells[("microsoft/Phi-3.5-mini-instruct", factor, level)]["overall"]
        b = cells[("Qwen/Qwen2.5-3B-Instruct", factor, level)]["overall"]
        h2h.append(
            {
                "config": config_labels[ci],
                "phi_acc": a["accuracy"],
                "phi_ci": a["accuracy_ci95"],
                "qwen_acc": b["accuracy"],
                "qwen_ci": b["accuracy_ci95"],
                "phi_minus_qwen_pp": pp(a["accuracy"] - b["accuracy"]),
                "ci_disjoint": not cis_overlap(a["accuracy_ci95"], b["accuracy_ci95"]),
                "winner": (
                    "Phi" if a["accuracy"] > b["accuracy"]
                    else ("Qwen" if b["accuracy"] > a["accuracy"] else "tie")
                ),
            }
        )
    out["ranking"]["phi_vs_qwen_head_to_head"] = h2h

    # Paired Phi-vs-Qwen McNemar per shared config. Both models answer the same
    # frozen items under the same configuration, so pairing by item id is exact;
    # this is the paired test that marginal Wilson-interval overlap cannot
    # substitute for.
    for ci, (factor, level) in enumerate(SHARED_CONFIGS):
        a_ids = cells[("microsoft/Phi-3.5-mini-instruct", factor, level)]["correct_by_id"]
        b_ids = cells[("Qwen/Qwen2.5-3B-Instruct", factor, level)]["correct_by_id"]
        shared = sorted(set(a_ids) & set(b_ids))
        h2h[ci]["mcnemar"] = mcnemar([a_ids[i] for i in shared], [b_ids[i] for i in shared])
        h2h[ci]["n_paired"] = len(shared)

    # Adjust the model-vs-model McNemar family (8 configs) with Holm.
    h2h_ps = [_raw_p(h['mcnemar']) for h in h2h]
    h2h_holm = holm_bonferroni(h2h_ps)
    for h, p_adj, raw in zip(h2h, h2h_holm, h2h_ps):
        h['mcnemar']['p_value'] = raw
        h["p_holm"] = p_adj
    out["ranking"]["phi_vs_qwen_head_to_head"] = h2h

    # ---------------------------------------------------------------- sampling
    sampling = {}
    for m in ["HuggingFaceTB/SmolLM2-1.7B-Instruct", "Qwen/Qwen2.5-3B-Instruct"]:
        short = SHORT_MODEL[m]
        ctrl = cells[(m, "control", "control")]
        ordered_ids = sorted(ctrl["correct_by_id"])
        seeds = {}
        for level in ["t0.7_seed0", "t0.7_seed1", "t0.7_seed2"]:
            c = cells.get((m, "sampled", level))
            if not c:
                continue
            mc = mcnemar(
                [ctrl["correct_by_id"][i] for i in ordered_ids],
                [c["correct_by_id"][i] for i in ordered_ids],
            )
            disagree_ids = [
                i for i in ordered_ids
                if ctrl["correct_by_id"][i] != c["correct_by_id"].get(i)
            ]
            seeds[level] = {
                "run_id": c["run_id"],
                "accuracy": c["overall"]["accuracy"],
                "ci95": c["overall"]["accuracy_ci95"],
                "correct": c["overall"]["correct"],
                "delta_pp_vs_control": pp(
                    c["overall"]["accuracy"] - ctrl["overall"]["accuracy"]
                ),
                "item_disagreement_rate": round(len(disagree_ids) / 800, 4),
                "mcnemar_p": mc["p_value"],
            }
        accs = [s["accuracy"] for s in seeds.values()]
        greedy_seeds = {}
        for level in ["1", "2"]:
            c = cells[(m, "seed", level)]
            mc = mcnemar(
                [ctrl["correct_by_id"][i] for i in ordered_ids],
                [c["correct_by_id"][i] for i in ordered_ids],
            )
            greedy_seeds[level] = {
                "accuracy": c["overall"]["accuracy"],
                "mcnemar": mc,
                "identical_to_control": mc["a_correct_b_wrong"] == 0
                and mc["a_wrong_b_correct"] == 0,
            }
        boot = bootstrap_ci_mean(accs, n_boot=2000, seed=0) if accs else None
        sampling[short] = {
            "control_accuracy": ctrl["overall"]["accuracy"],
            "sampled_seeds": seeds,
            "sampled_accs": accs,
            "sampled_std_pp": pp(pstdev(accs)) if len(accs) > 1 else None,
            "sampled_range_pp": pp(max(accs) - min(accs)) if accs else None,
            "bootstrap_ci_of_seed_mean": {
                "mean": round(boot["mean"], 4),
                "lo": round(boot["lo"], 4),
                "hi": round(boot["hi"], 4),
            }
            if boot
            else None,
            "greedy_seeds": greedy_seeds,
        }
    out["sampling"] = sampling

    # ----------------------------------------------------------------- latency
    latency = {}
    for m in MODELS_IN_MATRIX:
        for factor, level in [("control", "control"), ("backend", "vllm")]:
            c = cells.get((m, factor, level))
            if not c:
                continue
            lat = c.get("latency") or {}

            def _clean(v):
                return v if isinstance(v, (int, float)) and v and v > 0 else None

            usable = any(
                _clean(lat.get(k)) is not None
                for k in ("ttft_ms_mean", "e2e_ms_mean", "tokens_per_sec_mean")
            )
            latency[f"{SHORT_MODEL[m]}|{factor}={level}"] = {
                "run_id": c["run_id"],
                "status": "MEASURED" if usable else "UNAVAILABLE",
                "ttft_ms_mean": _clean(lat.get("ttft_ms_mean")),
                "e2e_ms_mean": _clean(lat.get("e2e_ms_mean")),
                "tokens_per_sec_mean": _clean(lat.get("tokens_per_sec_mean")),
                "raw": lat,
            }
    out["latency"] = latency

    # ---------------------------------------------------------------- failures
    failures = {}
    for m in MODELS_IN_MATRIX:
        for factor, level in SHARED_CONFIGS:
            c = cells.get((m, factor, level))
            if not c:
                continue
            blob_items = data["blobs"][c["run_id"]]["items"]
            counts = {cat: 0 for cat in CATEGORIES}
            for it in blob_items:
                counts[classify_item(it)] += 1
            key = f"{SHORT_MODEL[m]}|{factor}={level}"
            failures[key] = {
                "n": len(blob_items),
                "counts": counts,
                "correct_rate": round(counts["correct"] / len(blob_items), 4),
            }
    out["failures"] = failures

    # --------------------------------------------------------------------- ERS
    ers = evaluation_reliability_score(matrix, n_per_cell=800, n_boot=2000, seed=0)
    seed_scores = []
    for m in MODELS_IN_MATRIX:
        accs = []
        for level in ["1", "2"]:
            c = cells.get((m, "seed", level))
            accs.append(c["overall"]["accuracy"] if c else None)
        seed_scores.append(accs)
    ers_seed = evaluation_reliability_score(
        matrix, n_per_cell=800, seed_scores=seed_scores, n_boot=2000, seed=0
    )
    out["ers"] = {
        "matrix_8_configs": {
            "ers": round(ers["ers"], 4),
            "components": {
                k: round(v, 4) if isinstance(v, float) else v
                for k, v in ers["components"].items()
            },
            "components_used": ers.get("components_used"),
            "n_components": ers.get("n_components"),
            "bootstrap": {
                k: (round(v, 4) if isinstance(v, float) else v)
                for k, v in ers.get("bootstrap", {}).items()
            },
        },
        "with_seed_component": {
            "ers": round(ers_seed["ers"], 4),
            "components": {
                k: round(v, 4) if isinstance(v, float) else v
                for k, v in ers_seed["components"].items()
            },
        },
        "provisional": True,
    }

    # -------------------------------------------------------------- provenance
    planned = 34  # configs/experiments/stability.yaml --profile t4 cell count
    out["provenance"] = {
        "registry": "results/registry_paper.jsonl",
        "n_registry_ok": len(rows),
        "n_planned_t4_cells": planned,
        "n_missing_cells": planned - len(rows),
        "missing_cells": [
            {"model": "microsoft/Phi-3.5-mini-instruct", "factor": "sampled",
             "level": f"t0.7_seed{s}"} for s in (0, 1, 2)
        ],
        "git_commits": sorted({r["git_commit"] for r in rows if r.get("git_commit")}),
        "utc_first": min(r["utc"] for r in rows),
        "utc_last": max(r["utc"] for r in rows),
        "packages": data["verifications"][0]["packages"],
        "hardware_manifests": sorted(
            {
                json.dumps(v["hardware"], sort_keys=True)
                for v in data["verifications"]
                if v.get("hardware")
            }
        ),
        "python_versions": sorted(
            {v["hardware"]["python"] for v in data["verifications"] if v.get("hardware")}
        ),
        "model_revisions_recorded": sorted(
            {str(v["settings"].get("revision")) for v in data["verifications"]}
        ),
        "corrections_in_registry": [r["run_id"] for r in rows if r.get("correction")],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "statistics.json"
    out_path.write_text(json.dumps(out, indent=2, allow_nan=False), encoding="utf-8")
    print(f"wrote {out_path}")
    print(f"cells: {len(cells)}  contrasts: {len(contrasts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
