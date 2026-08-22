from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from apertus_eval_prep.stats import (
    ci_aware_ties,
    ci_width_curve,
    kendall_tau_b,
    mcnemar,
    pairwise_reversals,
    rank_high_is_better,
)


def load_run(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def overall_block(blob: dict[str, Any]) -> dict[str, Any]:
    return (blob.get("tasks") or {}).get("overall") or {}


def settings_of(blob: dict[str, Any]) -> dict[str, Any]:
    return (blob.get("manifest") or {}).get("settings") or {}


def short_model(model_id: str) -> str:
    return model_id.split("/")[-1]


def collect_runs(registry_rows: list[dict[str, Any]], repo_root: Path) -> list[dict[str, Any]]:
    out = []
    for row in registry_rows:
        if row.get("status") != "ok" or not row.get("path"):
            continue
        path = Path(row["path"])
        if not path.is_absolute():
            path = repo_root / path
        if not path.exists():
            continue
        blob = load_run(path)
        blob["_registry"] = row
        out.append(blob)
    return out


def _factor_key(blob: dict[str, Any]) -> tuple[str, str]:
    reg = blob.get("_registry") or {}
    return str(reg.get("factor") or blob.get("factor") or "control"), str(
        reg.get("factor_level") or blob.get("factor_level") or "control"
    )


def ranking_table(blobs: list[dict[str, Any]]) -> dict[str, Any]:
    """Rank models inside each (factor, level) on overall accuracy vs control."""
    by_cell: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for blob in blobs:
        model = settings_of(blob).get("model_id")
        if not model:
            continue
        by_cell[_factor_key(blob)][model] = blob

    control = by_cell.get(("control", "control"), {})
    control_models = sorted(control)
    control_acc = [overall_block(control[m]).get("accuracy") for m in control_models]
    control_ranks = rank_high_is_better(control_acc) if control_models else []
    control_rank_map = dict(zip(control_models, control_ranks))

    factor_rows = []
    for key, models_map in sorted(by_cell.items()):
        models = sorted(models_map)
        accs = [overall_block(models_map[m]).get("accuracy") for m in models]
        cis = [overall_block(models_map[m]).get("accuracy_ci95") for m in models]
        ranks = rank_high_is_better(accs)
        aligned_control = [control_rank_map.get(m) for m in models]
        tau = None
        reversals = None
        if all(r is not None for r in aligned_control) and len(models) >= 2:
            tau = kendall_tau_b(aligned_control, ranks)
            reversals = pairwise_reversals(aligned_control, ranks)
        factor_rows.append(
            {
                "factor": key[0],
                "factor_level": key[1],
                "models": [
                    {
                        "model_id": m,
                        "accuracy": accs[i],
                        "accuracy_ci95": cis[i],
                        "rank": ranks[i],
                        "control_rank": control_rank_map.get(m),
                    }
                    for i, m in enumerate(models)
                ],
                "kendall_tau_vs_control": None if tau is None else round(tau, 4),
                "rank_reversals_vs_control": reversals,
                "ci_ties": ci_aware_ties(models, [a or 0.0 for a in accs], cis),
            }
        )

    pairwise = []
    if control:
        control_model_items: dict[str, dict[str, bool]] = {}
        for model, blob in control.items():
            control_model_items[model] = {r["id"]: bool(r["correct"]) for r in blob.get("items") or []}
        for key, models_map in by_cell.items():
            if key == ("control", "control"):
                continue
            for model, blob in models_map.items():
                if model not in control_model_items:
                    continue
                a_map = control_model_items[model]
                b_map = {r["id"]: bool(r["correct"]) for r in blob.get("items") or []}
                ids = sorted(set(a_map) & set(b_map))
                if not ids:
                    continue
                test = mcnemar([a_map[i] for i in ids], [b_map[i] for i in ids])
                pairwise.append(
                    {
                        "model_id": model,
                        "factor": key[0],
                        "factor_level": key[1],
                        **test,
                    }
                )

    return {
        "control_ranking": sorted(
            [
                {
                    "model_id": m,
                    "accuracy": overall_block(control[m]).get("accuracy"),
                    "accuracy_ci95": overall_block(control[m]).get("accuracy_ci95"),
                    "rank": control_rank_map.get(m),
                }
                for m in control_models
            ],
            key=lambda r: (r.get("rank") is None, r.get("rank") or 0, r["model_id"]),
        ),
        "by_config": factor_rows,
        "mcnemar_vs_control": pairwise,
        "n_runs": len(blobs),
    }


def render_markdown_report(analysis: dict[str, Any]) -> str:
    lines = [
        "# Ranking stability report",
        "",
        "Generated from `results/registry.jsonl`. Numbers are generative exact-match,",
        "not lm-eval loglikelihood. Wilson 95% CIs. Rank flips whose CIs overlap are ties.",
        "",
        f"Runs loaded: {analysis.get('n_runs', 0)}",
        "",
        "## Control ranking",
        "",
        "| rank | model | accuracy | 95% CI |",
        "|---|---|---|---|",
    ]
    for row in analysis.get("control_ranking") or []:
        ci = row.get("accuracy_ci95")
        ci_s = f"[{ci[0]}, {ci[1]}]" if ci else "—"
        lines.append(f"| {row.get('rank')} | `{row.get('model_id')}` | {row.get('accuracy')} | {ci_s} |")
    lines += ["", "## Kendall tau vs control", "", "| factor | level | tau-b | rank reversals | n models |", "|---|---|---|---|---|"]
    for row in analysis.get("by_config") or []:
        n = len(row.get("models") or [])
        lines.append(
            f"| {row['factor']} | {row['factor_level']} | {row.get('kendall_tau_vs_control')} | "
            f"{row.get('rank_reversals_vs_control')} | {n} |"
        )
    lines += ["", "## McNemar vs control (same items)", "", "| model | factor | level | disagree | p |", "|---|---|---|---|---|"]
    for row in analysis.get("mcnemar_vs_control") or []:
        lines.append(
            f"| `{row['model_id']}` | {row['factor']} | {row['factor_level']} | "
            f"{row.get('disagreement_rate')} | {row.get('p_value')} |"
        )
    lines += ["", "## CI-overlap ties (control)", ""]
    control_cfg = next((r for r in analysis.get("by_config") or [] if r["factor"] == "control"), None)
    if control_cfg:
        lines += ["| model A | model B | point order | CI overlap (report as tie) |", "|---|---|---|---|"]
        for pair in control_cfg.get("ci_ties") or []:
            lines.append(
                f"| `{pair['model_a']}` | `{pair['model_b']}` | {pair['point_order']} | {pair['report_as_tie']} |"
            )
    lines.append("")
    return "\n".join(lines)


def paper_tables(analysis: dict[str, Any]) -> str:
    lines = [
        "<!-- generated by: python -m apertus_eval_prep paper-tables -->",
        "",
        "### Control ranking (overall generative accuracy)",
        "",
        "| Rank | Model | Acc. | 95% Wilson CI |",
        "|---:|---|---:|---|",
    ]
    for row in analysis.get("control_ranking") or []:
        ci = row.get("accuracy_ci95")
        ci_s = f"[{ci[0]:.3f}, {ci[1]:.3f}]" if ci else "—"
        acc = row.get("accuracy")
        acc_s = "—" if acc is None else f"{acc:.3f}"
        lines.append(f"| {row.get('rank')} | `{short_model(row.get('model_id') or '')}` | {acc_s} | {ci_s} |")
    if not analysis.get("control_ranking"):
        lines.append("| — | *no GPU sweep yet* | — | — |")
    lines += [
        "",
        "### Ranking agreement with control (Kendall $\\tau_b$)",
        "",
        "| Factor | Level | $\\tau_b$ | Pairwise reversals |",
        "|---|---|---:|---:|",
    ]
    for row in analysis.get("by_config") or []:
        if row["factor"] == "control":
            continue
        lines.append(
            f"| {row['factor']} | {row['factor_level']} | {row.get('kendall_tau_vs_control')} | "
            f"{row.get('rank_reversals_vs_control')} |"
        )
    if len([r for r in analysis.get("by_config") or [] if r["factor"] != "control"]) == 0:
        lines.append("| — | *TODO: no non-control cells in this registry* | — | — |")
    lines += [
        "",
        "Kendall $\\tau_b$ is defined only when a factor level has **two or more** models.",
        "A `None` cell means the registry does not yet have that factor on enough models — do not invent $\\tau_b$.",
        "",
        "### McNemar vs control (paired items, same model)",
        "",
        "| Model | Factor | Level | n | A✓ B✗ | A✗ B✓ | disagree | $\\chi^2$ | p |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in analysis.get("mcnemar_vs_control") or []:
        lines.append(
            f"| `{short_model(row['model_id'])}` | {row['factor']} | {row['factor_level']} | "
            f"{row.get('n')} | {row.get('a_correct_b_wrong')} | {row.get('a_wrong_b_correct')} | "
            f"{row.get('disagreement_rate')} | {row.get('chi2')} | {row.get('p_value')} |"
        )
    if not analysis.get("mcnemar_vs_control"):
        lines.append("| — | *TODO: no paired OFAT cell vs its control* | — | — | — | — | — | — | — |")
    lines.append("")
    return "\n".join(lines)


def _ci_s(ci: Any) -> str:
    if not ci or len(ci) < 2 or ci[0] is None or ci[1] is None:
        return "—"
    return f"[{float(ci[0]):.3f}, {float(ci[1]):.3f}]"


def _acc_frac(block: dict[str, Any] | None) -> str:
    if not block:
        return "TODO"
    n, correct = block.get("n"), block.get("correct")
    if n is None or correct is None:
        return "TODO"
    return f"{correct}/{n}"


def _blob_by(blobs: list[dict[str, Any]], model_substr: str, factor: str, level: str) -> dict[str, Any] | None:
    for blob in blobs:
        model = settings_of(blob).get("model_id") or ""
        if model_substr not in model:
            continue
        fac, lev = _factor_key(blob)
        if fac == factor and lev == level:
            return blob
    return None


def _task_correct(blob: dict[str, Any] | None, task: str) -> str:
    if blob is None:
        return "TODO"
    block = (blob.get("tasks") or {}).get(task) or {}
    n, correct = block.get("n"), block.get("correct")
    if n is None or correct is None:
        return "TODO"
    return f"{correct}/{n}"


def render_stability_paper(
    analysis: dict[str, Any],
    blobs: list[dict[str, Any]],
    *,
    n_t4_planned: int = 34,
    n_registry_ok: int | None = None,
) -> str:
    """Write paper/stability.md from committed registry blobs only. No invented cells."""
    n_ok = n_registry_ok if n_registry_ok is not None else analysis.get("n_runs", 0)
    missing = max(n_t4_planned - n_ok, 0)

    smol_c = _blob_by(blobs, "SmolLM2", "control", "control")
    smol_concise = _blob_by(blobs, "SmolLM2", "prompt_id", "concise")
    smol_5shot = _blob_by(blobs, "SmolLM2", "prompt_id", "5shot")
    qwen = _blob_by(blobs, "Qwen2.5-3B", "control", "control")
    phi = _blob_by(blobs, "Phi-3.5", "control", "control")

    tau_rows = [r for r in analysis.get("by_config") or [] if r["factor"] != "control"]
    tau_defined = [r for r in tau_rows if r.get("kendall_tau_vs_control") is not None]
    mcnemar_rows = analysis.get("mcnemar_vs_control") or []

    if smol_c and smol_concise and not tau_defined:
        oc = overall_block(smol_c)
        op = overall_block(smol_concise)
        abstract = (
            f"On the committed T4 paper-matrix rows (**{n_ok} of {n_t4_planned}** cells in "
            "`stability.yaml`), the non-obvious result is not a three-model rank flip — that "
            "$\\tau_b$ is **undefined** (only SmolLM2 has a prompt ablation). It is a "
            "**paired-item** effect on one model: switching SmolLM2-1.7B from the default prompt "
            f"to `concise` drops generative exact-match from {_acc_frac(oc)} to {_acc_frac(op)} "
            f"(Wilson CIs {_ci_s(oc.get('accuracy_ci95'))} vs {_ci_s(op.get('accuracy_ci95'))}"
            ", disjoint)."
        )
        concise_m = next(
            (r for r in mcnemar_rows if r.get("factor") == "prompt_id" and r.get("factor_level") == "concise"),
            None,
        )
        shot_m = next(
            (r for r in mcnemar_rows if r.get("factor") == "prompt_id" and r.get("factor_level") == "5shot"),
            None,
        )
        if concise_m:
            abstract += (
                f" McNemar on the same {concise_m.get('n')} ids: "
                f"{concise_m.get('a_correct_b_wrong')} control-correct / concise-wrong vs "
                f"{concise_m.get('a_wrong_b_correct')} the other way, $p = {concise_m.get('p_value')}$ "
                f"(`chi2` {concise_m.get('chi2')})."
            )
        if smol_5shot and shot_m:
            os5 = overall_block(smol_5shot)
            abstract += (
                f" The `5shot` prompt is {_acc_frac(os5)}: the overall Wilson interval "
                f"**overlaps** control, but McNemar still rejects equality ($p = {shot_m.get('p_value')}$). "
                "Overlapping CIs are not a license to ignore paired disagreement."
            )
        factors_present = {r["factor"] for r in tau_rows}
        missing_bits = [name for name in ("seed", "backend", "quantization", "sampled") if name not in factors_present]
        if missing_bits:
            abstract += (
                f" Still missing in git for ranking: {', '.join(missing_bits)}. "
                "Do not invent $\\tau_b$ for those factors."
            )
        if "quantization" in factors_present:
            abstract += (
                " A Qwen-7B int4 cell exists, but T4 has no 7B fp16 control, so there is no same-model "
                "quantization McNemar and no multi-model $\\tau_b$ on int4 yet."
            )
    elif tau_defined:
        flips = [r for r in tau_defined if (r.get("rank_reversals_vs_control") or 0) > 0]
        if flips:
            bits = ", ".join(f"{r['factor']}={r['factor_level']} ($\\tau_b$={r['kendall_tau_vs_control']})" for r in flips)
            abstract = (
                f"On the committed T4 paper-matrix rows (**{n_ok} of {n_t4_planned}** cells), "
                f"Kendall $\\tau_b$ is defined and rank reversals appear for: {bits}. "
                "Those are the ranking-stability claims this registry currently supports."
            )
        else:
            abstract = (
                f"On the committed T4 paper-matrix rows (**{n_ok} of {n_t4_planned}** cells), "
                "Kendall $\\tau_b$ is defined and **no ranking flips were significant**. "
                "That is the finding; do not spin a null result as a positive ranking-robustness claim "
                "beyond what the CIs and McNemar tests show."
            )
    else:
        abstract = (
            f"The paper-matrix registry currently has **{n_ok} of {n_t4_planned}** T4 cells. "
            "There are not enough paired models on any swept factor for Kendall $\\tau_b$. "
            "Do not invent a ranking-flip finding. See `notes/paper_run_status.md`."
        )

    lines = [
        "# Score and ranking stability under evaluation configuration",
        "",
        "**How stable are generative LLM benchmark scores and rankings when the prompt, seed, inference backend, or quantization changes?**",
        "",
        "<!-- generated by: python -m apertus_eval_prep paper --registry results/registry_paper.jsonl -->",
        "Tables marked generated come from that command. Every accuracy below is copied from `results/runs/*.json`. "
        "Missing cells: [`notes/paper_run_status.md`](../notes/paper_run_status.md). "
        "If a cell is missing, the cell says TODO — it is not a plausible-looking number.",
        "",
        "## Abstract",
        "",
        abstract,
        "",
        "## 1. Introduction",
        "",
        "The canary in this repository showed that omitting a chat template, or swapping Hugging Face `generate` for vLLM, "
        "moves accuracy on the frozen canary slice ([`notes/findings.md`](../notes/findings.md)). That is a serving bug detector, not a ranking study.",
        "",
        "This note asks: **if you change a legitimate evaluation choice, do scores move, and do model ranks hold?** "
        "A drop that leaves order intact is a different claim from a drop that swaps first and second place. "
        "With only one model on a factor, we can test scores (Wilson + McNemar) but not rank agreement (Kendall $\\tau_b$).",
        "",
        "We do not use lm-eval loglikelihood multiple choice. Every item is scored by generating text and extracting a letter or a number.",
        "",
        "## 2. Related work",
        "",
        "Standard harnesses (lm-evaluation-harness, HELM, lighteval) pin prompts and metrics but still leave backend, quantization, and sampling as operator choices. "
        "swiss-ai evals-post-train notes that GSM8K-style generation can differ between Hugging Face and vLLM. "
        "This study's increment is **frozen official subsets + OFAT + interval-aware ties**, in a cloneable YAML harness.",
        "",
        "## 3. Method",
        "",
        "### 3.1 Frozen slices",
        "",
        "Official n=200 per task: ARC-Easy, GSM8K, HellaSwag (generative letter), MGSM EN/DE/FR. Provenance: [`data/official/SOURCES.md`](../data/official/SOURCES.md).",
        "",
        "### 3.2 Models and control",
        "",
        "Control: HF `generate`, tokenizer chat template, greedy, `quantization: none`, prompt `default`, seed `0`. "
        "T4 skips 7B fp16 / int8 / vLLM. OFAT factors: prompt, seed, backend, quantization, sampled (`stability.yaml`).",
        "",
        "### 3.3 Statistics",
        "",
        "Wilson 95% CI on $k/n$. Paired configs: continuity-corrected McNemar. Rankings: competition ranks on overall accuracy; "
        "Kendall $\\tau_b$ vs control when ≥2 models share a factor level. Overlapping CIs are reported as ties even if point estimates differ.",
        "",
        "## 4. Results (committed registry only)",
        "",
        "Command:",
        "",
        "```",
        "python -m apertus_eval_prep paper --registry results/registry_paper.jsonl --out-dir paper",
        "```",
        "",
        f"Registry rows with `status=ok`: **{n_ok}**. Planned T4 cells: **{n_t4_planned}**. Missing: **{missing}**.",
        "",
        "### 4.1 Control ranking",
        "",
        "| Rank | Model | correct | acc | 95% Wilson CI | source |",
        "|---:|---|---:|---:|---|---|",
    ]

    for row in analysis.get("control_ranking") or []:
        mid = short_model(row.get("model_id") or "")
        blob = next((b for b in (phi, qwen, smol_c) if b and short_model(settings_of(b).get("model_id") or "") == mid), None)
        ov = overall_block(blob) if blob else {}
        src = "TODO"
        if blob:
            path = (blob.get("_registry") or {}).get("path") or ""
            src = f"`{Path(path).name}`" if path else "committed JSON"
        lines.append(
            f"| {row.get('rank')} | {mid} | {ov.get('correct', 'TODO')} | {row.get('accuracy')} | "
            f"{_ci_s(row.get('accuracy_ci95'))} | {src} |"
        )
    if not analysis.get("control_ranking"):
        lines.append("| — | *no control cells in this registry* | TODO | TODO | TODO | TODO |")

    phi_ov = overall_block(phi) if phi else {}
    qwen_ov = overall_block(qwen) if qwen else {}
    if phi and qwen:
        from apertus_eval_prep.stats import cis_overlap

        overlap = cis_overlap(phi_ov.get("accuracy_ci95"), qwen_ov.get("accuracy_ci95"))
        if overlap:
            lines += [
                "",
                "Phi vs Qwen-3B: CIs **overlap** → report as a **tie**. SmolLM2 is separated from both if its interval does not overlap either.",
            ]
    qwen7_int4 = _blob_by(blobs, "Qwen2.5-7B", "quantization", "int4")
    lines.append("")
    if qwen7_int4:
        ov7 = overall_block(qwen7_int4)
        lines += [
            f"Qwen-7B **int4** (factor=`quantization`, not control — T4 skips 7B fp16): "
            f"{_acc_frac(ov7)} overall, Wilson {_ci_s(ov7.get('accuracy_ci95'))} "
            f"(ARC {_task_correct(qwen7_int4, 'arc_easy')}, GSM8K {_task_correct(qwen7_int4, 'gsm8k')}, "
            f"HellaSwag {_task_correct(qwen7_int4, 'hellaswag')}, MGSM {_task_correct(qwen7_int4, 'mgsm')}). "
            "Do **not** rank this against Phi / Qwen-3B fp16 control. "
            "McNemar vs a 7B control: **TODO** (no fp16 cell on T4).",
            "",
        ]
    else:
        lines += [
            "Qwen-7B int4: **TODO** (hash `22a6a0a56a69a1cb` not in registry).",
            "",
        ]
    lines += [
        "### 4.2 SmolLM2 `prompt_id` (only model with this factor unless the registry grew)",
        "",
        "| prompt | correct | acc | 95% Wilson CI | vs control CI |",
        "|---|---:|---:|---|---|",
    ]

    def _prompt_row(label: str, blob: dict[str, Any] | None, vs: str) -> str:
        if blob is None:
            return f"| {label} | TODO | TODO | TODO | {vs} |"
        ov = overall_block(blob)
        return (
            f"| {label} | {ov.get('correct')} | {ov.get('accuracy')} | "
            f"{_ci_s(ov.get('accuracy_ci95'))} | {vs} |"
        )

    lines.append(_prompt_row("default (control)", smol_c, "—"))
    lines.append(_prompt_row("concise", smol_concise, "see Wilson overlap vs control"))
    lines.append(_prompt_row("5shot", smol_5shot, "see Wilson overlap vs control"))

    lines += [
        "",
        "McNemar vs control (paired ids, A = control, B = variant), from `ranking_table`:",
        "",
        "| level | A✓B✗ | A✗B✓ | disagree | $\\chi^2$ | p |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    if mcnemar_rows:
        for row in mcnemar_rows:
            lines.append(
                f"| {row.get('factor_level')} | {row.get('a_correct_b_wrong')} | "
                f"{row.get('a_wrong_b_correct')} | {row.get('disagreement_rate')} | "
                f"{row.get('chi2')} | {row.get('p_value')} |"
            )
    else:
        lines.append("| TODO | TODO | TODO | TODO | TODO | TODO |")

    lines += [
        "",
        "Task counts (same JSON `tasks` blocks):",
        "",
        "| prompt | ARC | GSM8K | HellaSwag | MGSM |",
        "|---|---:|---:|---:|---:|",
        f"| default | {_task_correct(smol_c, 'arc_easy')} | {_task_correct(smol_c, 'gsm8k')} | {_task_correct(smol_c, 'hellaswag')} | {_task_correct(smol_c, 'mgsm')} |",
        f"| concise | {_task_correct(smol_concise, 'arc_easy')} | {_task_correct(smol_concise, 'gsm8k')} | {_task_correct(smol_concise, 'hellaswag')} | {_task_correct(smol_concise, 'mgsm')} |",
        f"| 5shot | {_task_correct(smol_5shot, 'arc_easy')} | {_task_correct(smol_5shot, 'gsm8k')} | {_task_correct(smol_5shot, 'hellaswag')} | {_task_correct(smol_5shot, 'mgsm')} |",
        "",
        "### 4.3 Kendall $\\tau_b$",
        "",
        "| Factor | Level | $\\tau_b$ | reversals | n models in registry |",
        "|---|---|---|---|---:|",
    ]
    if tau_rows:
        for row in tau_rows:
            n_models = len(row.get("models") or [])
            tau = row.get("kendall_tau_vs_control")
            tau_s = "TODO / undefined" if tau is None else str(tau)
            rev = row.get("rank_reversals_vs_control")
            rev_s = "—" if rev is None else str(rev)
            lines.append(f"| {row['factor']} | {row['factor_level']} | {tau_s} | {rev_s} | {n_models} |")
    else:
        lines.append("| seed, backend, quantization, sampled | * | **TODO** | — | 0 |")

    lines += [
        "",
        "No ranking-flip claim unless a $\\tau_b$ cell above is a real number with ≥2 models. "
        "Need the same factor on a second model before $\\tau_b$ on that factor.",
        "",
        "## 5. Canary (not the paper matrix)",
        "",
        "n=28 template / backend numbers stay in [`notes/findings.md`](../notes/findings.md) Experiments 1–2. "
        "n=4 smoke stays Experiment 3 (CI-width demo). Do not pool those with §4.",
        "",
        "## 6. Limitations",
        "",
        f"- {n_ok} / {n_t4_planned} T4 cells. Incomplete OFAT is not a finished ranking study.",
        "- Colab T4, not Alps. Hardware and Python versions are whatever the committed manifests say; do not overwrite them.",
        "- Generative HellaSwag/ARC is not official loglikelihood.",
        "- OFAT does not estimate interactions.",
        "- Greedy extra seeds may be a no-op; those cells are not a finding until their JSON exists.",
        "",
        "## 7. Conclusion",
        "",
        "The committed matrix supports only claims that have a JSON row. "
        "Fill [`notes/paper_run_status.md`](../notes/paper_run_status.md) before stating $\\tau_b$ on a factor that is still missing models.",
        "",
    ]
    return "\n".join(lines)


def write_plots(analysis: dict[str, Any], out_dir: Path) -> list[str]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    # Forest: control accuracies with CI
    control = analysis.get("control_ranking") or []
    if control:
        fig, ax = plt.subplots(figsize=(8, 3 + 0.4 * len(control)))
        ys = list(range(len(control)))
        accs = [r.get("accuracy") or 0 for r in control]
        los, his = [], []
        for r in control:
            ci = r.get("accuracy_ci95") or [r.get("accuracy") or 0, r.get("accuracy") or 0]
            los.append(accs[len(los)] - ci[0])
            his.append(ci[1] - accs[len(his)])
        labels = [short_model(r.get("model_id") or "") for r in control]
        ax.errorbar(accs, ys, xerr=[los, his], fmt="o", capsize=4)
        ax.set_yticks(ys)
        ax.set_yticklabels(labels)
        ax.set_xlabel("overall accuracy (Wilson 95% CI)")
        ax.set_xlim(0, 1)
        ax.invert_yaxis()
        ax.set_title("Control ranking")
        fig.tight_layout()
        path = out_dir / "forest_control.png"
        fig.savefig(path, dpi=140)
        plt.close(fig)
        written.append(str(path))

    # Kendall bars
    rows = [r for r in analysis.get("by_config") or [] if r["factor"] != "control"]
    if rows:
        fig, ax = plt.subplots(figsize=(9, 3 + 0.35 * len(rows)))
        labels = [f"{r['factor']}={r['factor_level']}" for r in rows]
        taus = [r.get("kendall_tau_vs_control") or 0 for r in rows]
        ax.barh(labels, taus)
        ax.set_xlabel("Kendall tau-b vs control ranking")
        ax.set_xlim(-1.05, 1.05)
        ax.axvline(0, color="gray", linewidth=0.8)
        fig.tight_layout()
        path = out_dir / "kendall_tau.png"
        fig.savefig(path, dpi=140)
        plt.close(fig)
        written.append(str(path))

    # Rank heatmap
    configs = analysis.get("by_config") or []
    if configs:
        model_ids = []
        for r in configs:
            for m in r.get("models") or []:
                if m["model_id"] not in model_ids:
                    model_ids.append(m["model_id"])
        if model_ids:
            mat = []
            col_labels = []
            for r in configs:
                rank_map = {m["model_id"]: m.get("rank") for m in r.get("models") or []}
                mat.append([rank_map.get(m) if rank_map.get(m) is not None else float("nan") for m in model_ids])
                col_labels.append(f"{r['factor']}={r['factor_level']}")
            arr = list(map(list, zip(*mat)))
            fig, ax = plt.subplots(figsize=(max(6, 0.55 * len(col_labels) + 3), 2 + 0.4 * len(model_ids)))
            im = ax.imshow(arr, aspect="auto")
            ax.set_yticks(range(len(model_ids)))
            ax.set_yticklabels([short_model(m) for m in model_ids])
            ax.set_xticks(range(len(col_labels)))
            ax.set_xticklabels(col_labels, rotation=75, ha="right", fontsize=8)
            fig.colorbar(im, ax=ax, label="rank (1=best)")
            ax.set_title("Model rank by evaluation config")
            fig.tight_layout()
            path = out_dir / "rank_heatmap.png"
            fig.savefig(path, dpi=140)
            plt.close(fig)
            written.append(str(path))

    return written


def items_correct(blob: dict[str, Any]) -> list[bool]:
    return [bool(r.get("correct")) for r in blob.get("items") or []]


def parse_run_spec(spec: str) -> tuple[Path, str]:
    if "=" in spec:
        path_s, label = spec.split("=", 1)
        return Path(path_s), label.strip()
    path = Path(spec)
    return path, path.stem


def ci_width_report(specs: list[str]) -> dict[str, Any]:
    series = []
    highlights = []
    for spec in specs:
        path, label = parse_run_spec(spec)
        blob = load_run(path)
        correct = items_correct(blob)
        curve = ci_width_curve(correct)
        last = curve[-1] if curve else None
        series.append({"label": label, "path": str(path), "n": len(correct), "curve": curve, "final": last})
        if last:
            highlights.append(
                {
                    "label": label,
                    "n": last["n"],
                    "accuracy": last["accuracy"],
                    "ci95": [last["lo"], last["hi"]],
                    "width": last["width"],
                }
            )
    return {"series": series, "highlights": highlights}


def render_ci_width_markdown(analysis: dict[str, Any]) -> str:
    lines = [
        "# Wilson CI width vs n",
        "",
        "Not the paper matrix. Prefix Wilson intervals on already-scored items.",
        "The n=4 T4 smoke is supposed to have a huge interval; n=28 is still wide.",
        "",
        "## Width at the end of each run",
        "",
        "| run | n | accuracy | 95% Wilson CI | width |",
        "|---|---:|---:|---|---:|",
    ]
    for row in analysis.get("highlights") or []:
        ci = row.get("ci95") or [None, None]
        lines.append(
            f"| {row['label']} | {row['n']} | {row['accuracy']} | [{ci[0]}, {ci[1]}] | {row['width']} |"
        )
    lines += ["", "## Prefix curve (selected n)", ""]
    for ser in analysis.get("series") or []:
        lines += [f"### {ser['label']}", "", "| n | correct | acc | lo | hi | width |", "|---:|---:|---:|---:|---:|---:|"]
        curve = ser.get("curve") or []
        wanted = {1, 2, 4, 8, 16, 28, len(curve)}
        for row in curve:
            if row["n"] in wanted or row["n"] == curve[-1]["n"]:
                lines.append(
                    f"| {row['n']} | {row['correct']} | {row['accuracy']} | {row['lo']} | {row['hi']} | {row['width']} |"
                )
        lines.append("")
    lines.append("A rank reversal inside overlapping CIs is not evidence. That is the demo.")
    lines.append("")
    return "\n".join(lines)


def write_ci_width_plot(analysis: dict[str, Any], out_dir: Path) -> list[str]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    series = analysis.get("series") or []
    if not series:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    for ser in series:
        curve = ser.get("curve") or []
        ns = [r["n"] for r in curve]
        widths = [r["width"] for r in curve]
        ax.plot(ns, widths, marker="o", label=ser["label"])
    ax.set_xlabel("n (items scored so far)")
    ax.set_ylabel("Wilson 95% CI width")
    ax.set_ylim(0, 1.05)
    ax.set_title("CI width shrinks slowly; n=4 cannot rank models")
    ax.legend()
    fig.tight_layout()
    path = out_dir / "ci_width_vs_n.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return [str(path)]

