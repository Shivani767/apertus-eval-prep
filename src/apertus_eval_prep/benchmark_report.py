from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apertus_eval_prep.analysis import (
    build_pareto_from_runs,
    cost_performance_metrics,
    multilingual_analysis,
    paraphrase_robustness,
    quantization_comparison,
    thinking_comparison,
)
from apertus_eval_prep.report import load_run, parse_run_spec, short_model
from apertus_eval_prep.stats import kendall_tau_b, rank_high_is_better


def _settings(blob: dict[str, Any]) -> dict[str, Any]:
    return (blob.get("manifest") or {}).get("settings") or {}


def _overall(blob: dict[str, Any]) -> dict[str, Any]:
    return (blob.get("tasks") or {}).get("overall") or {}


def analyze_runs(specs: list[str]) -> dict[str, Any]:
    """Build a multi-run benchmark summary from scored JSON paths or path=label specs."""
    runs: list[dict[str, Any]] = []
    for spec in specs:
        path, label = parse_run_spec(spec)
        blob = load_run(path)
        settings = _settings(blob)
        runs.append(
            {
                "label": label,
                "path": str(path),
                "model_id": settings.get("model_id"),
                "backend": settings.get("backend"),
                "quantization": settings.get("quantization", "none"),
                "thinking_mode": bool(settings.get("thinking_mode", False)),
                "prompt_id": settings.get("prompt_id"),
                "paraphrase_id": settings.get("paraphrase_id"),
                "temperature": settings.get("temperature", 0.0),
                "overall": _overall(blob),
                "tasks": blob.get("tasks") or {},
                "language": blob.get("language") or {},
                "latency": blob.get("latency") or {},
                "cost": blob.get("cost"),
                "items": blob.get("items") or [],
                "_blob": blob,
            }
        )

    models = sorted({r["model_id"] for r in runs if r.get("model_id")})
    accs = []
    for mid in models:
        row = next((r for r in runs if r["model_id"] == mid), None)
        accs.append((row or {}).get("overall", {}).get("accuracy") or 0.0)
    ranks = rank_high_is_better(accs) if models else []
    rank_map = dict(zip(models, ranks))

    thinking_pairs = []
    thinking_derived = []
    by_model_think: dict[str, dict[bool, dict]] = {}
    for r in runs:
        mid = r.get("model_id")
        if not mid:
            continue
        by_model_think.setdefault(mid, {})[bool(r.get("thinking_mode"))] = r
    for mid, pair in by_model_think.items():
        if True in pair and False in pair:
            nt_blob = pair[False]["_blob"]
            th_blob = pair[True]["_blob"]
            derived = thinking_comparison(nt_blob, th_blob)
            derived["model_id"] = mid
            thinking_derived.append(derived)
            thinking_pairs.append(
                {
                    "model_id": mid,
                    "non_thinking_acc": derived.get("non_thinking_accuracy"),
                    "thinking_acc": derived.get("thinking_accuracy"),
                    "delta_pp": derived.get("reasoning_gain"),
                    "reasoning_gain_pp": derived.get("reasoning_gain_pp"),
                    "additional_tokens": derived.get("additional_tokens"),
                    "reasoning_efficiency": derived.get("reasoning_efficiency"),
                }
            )

    quant_rows = []
    quant_derived = []
    by_model_quant: dict[str, dict[str, dict]] = {}
    for r in runs:
        mid = r.get("model_id")
        if not mid:
            continue
        by_model_quant.setdefault(mid, {})[str(r.get("quantization") or "none")] = r
    for mid, levels in by_model_quant.items():
        fp16 = levels.get("none")
        if not fp16:
            continue
        for q in ("int8", "int4"):
            if q not in levels:
                continue
            derived = quantization_comparison(fp16["_blob"], levels[q]["_blob"], quant_label=q)
            derived["model_id"] = mid
            quant_derived.append(derived)
            quant_rows.append(
                {
                    "model_id": mid,
                    "quantization": q,
                    "fp16_acc": derived.get("fp16_accuracy"),
                    "quant_acc": derived.get("quant_accuracy"),
                    "delta_pp": derived.get("accuracy_delta"),
                    "tps_fp16": derived.get("fp16_tokens_per_sec"),
                    "tps_quant": derived.get("quant_tokens_per_sec"),
                    "throughput_change_ratio": derived.get("throughput_change_ratio"),
                }
            )

    paraphrase_rows = []
    paraphrase_derived: dict[str, Any] = {}
    by_model_para: dict[str, list[dict]] = {}
    for r in runs:
        mid = r.get("model_id")
        if not mid:
            continue
        by_model_para.setdefault(mid, []).append(r["_blob"])
    for mid, blobs in by_model_para.items():
        if len(blobs) < 2:
            continue
        rob = paraphrase_robustness(blobs)
        if rob:
            paraphrase_derived[mid] = rob
        orig = next((r for r in runs if r.get("model_id") == mid and (r.get("paraphrase_id") or "orig") == "orig"), None)
        for r in runs:
            if r.get("model_id") != mid:
                continue
            pid = r.get("paraphrase_id") or "orig"
            if pid == "orig":
                continue
            paraphrase_rows.append(
                {
                    "model_id": mid,
                    "paraphrase_id": pid,
                    "orig_acc": (orig or {}).get("overall", {}).get("accuracy"),
                    "variant_acc": r.get("overall", {}).get("accuracy"),
                    "delta_pp": round(
                        (r.get("overall", {}).get("accuracy") or 0)
                        - ((orig or {}).get("overall", {}).get("accuracy") or 0),
                        4,
                    ),
                }
            )

    cost_perf = []
    cost_derived = []
    for r in runs:
        eff = cost_performance_metrics(r["_blob"])
        eff["label"] = r["label"]
        eff["model_id"] = r.get("model_id")
        cost_derived.append(eff)
        cost = r.get("cost") or {}
        acc = r.get("overall", {}).get("accuracy")
        if cost.get("usd_total") is not None and acc is not None:
            cost_perf.append(
                {
                    "label": r["label"],
                    "model_id": r.get("model_id"),
                    "accuracy": acc,
                    "usd_total": cost.get("usd_total"),
                    "usd_per_item": cost.get("usd_per_item"),
                    "tokens_per_sec_mean": r.get("latency", {}).get("tokens_per_sec_mean"),
                    "acc_per_usd": eff.get("accuracy_per_cost_estimated"),
                    "accuracy_per_second_measured": eff.get("accuracy_per_second_measured"),
                }
            )

    multilingual_derived = [
        {"label": r["label"], "model_id": r.get("model_id"), **multilingual_analysis(r.get("language") or {})}
        for r in runs
        if r.get("language")
    ]

    pareto = build_pareto_from_runs([r["_blob"] for r in runs])

    task_names = sorted({t for r in runs for t in (r.get("tasks") or {}) if t != "overall"})
    comparison = []
    for r in runs:
        row = {
            "label": r["label"],
            "model_id": r.get("model_id"),
            "rank": rank_map.get(r.get("model_id")),
            "overall_acc": r.get("overall", {}).get("accuracy"),
            "overall_ci95": r.get("overall", {}).get("accuracy_ci95"),
        }
        for task in task_names:
            block = (r.get("tasks") or {}).get(task) or {}
            row[f"{task}_acc"] = block.get("accuracy")
        comparison.append(row)

    model_accs = [rank_map[m] for m in models]
    tau = kendall_tau_b(list(range(1, len(models) + 1)), model_accs) if len(models) >= 2 else None

    return {
        "n_runs": len(runs),
        "models": models,
        "comparison": comparison,
        "thinking_vs_non_thinking": thinking_pairs,
        "thinking_derived": thinking_derived,
        "quantization": quant_rows,
        "quantization_derived": quant_derived,
        "paraphrase_robustness": paraphrase_rows,
        "paraphrase_derived": paraphrase_derived,
        "cost_performance": cost_perf,
        "cost_derived": cost_derived,
        "multilingual_derived": multilingual_derived,
        "pareto": pareto,
        "multilingual": [{**r, "languages": r.get("language")} for r in runs if r.get("language")],
        "hallucination": [
            {
                "label": r["label"],
                "model_id": r.get("model_id"),
                **((r.get("tasks") or {}).get("hallucination") or {}),
            }
            for r in runs
            if (r.get("tasks") or {}).get("hallucination")
        ],
        "safety_bias": [
            {
                "label": r["label"],
                "model_id": r.get("model_id"),
                **((r.get("tasks") or {}).get("safety_bias") or {}),
            }
            for r in runs
            if (r.get("tasks") or {}).get("safety_bias")
        ],
        "robustness": [
            {
                "label": r["label"],
                "model_id": r.get("model_id"),
                **((r.get("tasks") or {}).get("robustness") or {}),
            }
            for r in runs
            if (r.get("tasks") or {}).get("robustness")
        ],
        "kendall_tau_model_order": tau,
    }


def render_benchmark_report(analysis: dict[str, Any]) -> str:
    lines = [
        "# Benchmark comparison report",
        "",
        "Auto-generated from scored run JSON. Generative exact-match unless noted.",
        f"Runs loaded: **{analysis.get('n_runs', 0)}**.",
        "",
        "## Multi-model comparison",
        "",
        "| label | model | rank | overall acc | 95% CI |",
        "|---|---|---:|---:|---|",
    ]
    for row in analysis.get("comparison") or []:
        ci = row.get("overall_ci95")
        ci_s = f"[{ci[0]}, {ci[1]}]" if ci else "—"
        lines.append(
            f"| {row.get('label')} | `{short_model(row.get('model_id') or '')}` | "
            f"{row.get('rank')} | {row.get('overall_acc')} | {ci_s} |"
        )

    task_cols = sorted(
        {
            k.replace("_acc", "")
            for row in analysis.get("comparison") or []
            for k in row
            if k.endswith("_acc") and k != "overall_acc"
        }
    )
    if task_cols:
        lines += ["", "### Per-task accuracy", "", "| label | " + " | ".join(task_cols) + " |", "|---|" + "---|" * len(task_cols)]
        for row in analysis.get("comparison") or []:
            cells = " | ".join(str(row.get(f"{t}_acc", "—")) for t in task_cols)
            lines.append(f"| {row.get('label')} | {cells} |")

    lines += ["", "## Multilingual breakdown", ""]
    ml = analysis.get("multilingual") or []
    if ml:
        langs = sorted({lang for r in ml for lang in (r.get("languages") or {})})
        lines += ["| run | " + " | ".join(langs) + " |", "|---|" + "---|" * len(langs)]
        for r in ml:
            cells = " | ".join(str((r.get("languages") or {}).get(lang, {}).get("accuracy", "—")) for lang in langs)
            lines.append(f"| {r.get('label')} | {cells} |")
    else:
        lines.append("_No language summaries in loaded runs._")

    lines += ["", "## Thinking vs non-thinking", ""]
    think = analysis.get("thinking_vs_non_thinking") or []
    if think:
        lines += [
            "| model | non-thinking | thinking | Δ pp |",
            "|---|---:|---:|---:|",
        ]
        for row in think:
            lines.append(
                f"| `{short_model(row['model_id'])}` | {row.get('non_thinking_acc')} | "
                f"{row.get('thinking_acc')} | {row.get('delta_pp')} |"
            )
    else:
        lines.append("_Pair runs with `thinking_mode: true/false` on the same model._")

    lines += ["", "## Prompt robustness (paraphrase)", ""]
    para = analysis.get("paraphrase_robustness") or []
    if para:
        lines += ["| model | variant | orig acc | variant acc | Δ pp |", "|---|---|---:|---:|---:|"]
        for row in para:
            lines.append(
                f"| `{short_model(row['model_id'])}` | {row.get('paraphrase_id')} | "
                f"{row.get('orig_acc')} | {row.get('variant_acc')} | {row.get('delta_pp')} |"
            )
    else:
        lines.append("_Run paraphrase_id OFAT cells (`orig`, `p1`, `p2`) to populate._")

    lines += ["", "## Hallucination (fact verification F1)", ""]
    hall = analysis.get("hallucination") or []
    if hall:
        lines += ["| run | model | acc | F1 | precision | recall |", "|---|---|---:|---:|---:|---:|"]
        for row in hall:
            lines.append(
                f"| {row.get('label')} | `{short_model(row.get('model_id') or '')}` | "
                f"{row.get('accuracy')} | {row.get('f1')} | {row.get('precision')} | {row.get('recall')} |"
            )
    else:
        lines.append("_Include `hallucination` task in eval config._")

    lines += ["", "## Safety and bias", ""]
    safe = analysis.get("safety_bias") or []
    if safe:
        lines += [
            "| run | model | refusal recall | over-refusal | benign acc |",
            "|---|---|---:|---:|---:|",
        ]
        for row in safe:
            lines.append(
                f"| {row.get('label')} | `{short_model(row.get('model_id') or '')}` | "
                f"{row.get('refusal_recall')} | {row.get('over_refusal_rate')} | {row.get('benign_accuracy')} |"
            )
    else:
        lines.append("_Include `safety_bias` task in eval config._")

    lines += ["", "## Robustness (noisy prompts)", ""]
    rob = analysis.get("robustness") or []
    if rob:
        lines += ["| run | model | accuracy |", "|---|---|---:|"]
        for row in rob:
            lines.append(f"| {row.get('label')} | `{short_model(row.get('model_id') or '')}` | {row.get('accuracy')} |")
    else:
        lines.append("_Include `robustness` task in eval config._")

    lines += ["", "## Quantization evaluation", ""]
    quant = analysis.get("quantization") or []
    if quant:
        lines += [
            "| model | quant | fp16 acc | quant acc | Δ pp | fp16 tps | quant tps |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
        for row in quant:
            lines.append(
                f"| `{short_model(row['model_id'])}` | {row.get('quantization')} | "
                f"{row.get('fp16_acc')} | {row.get('quant_acc')} | {row.get('delta_pp')} | "
                f"{row.get('tps_fp16')} | {row.get('tps_quant')} |"
            )
    else:
        lines.append("_Pair fp16 control with int8/int4 on the same model._")

    lines += ["", "## Cost–performance", ""]
    cp = analysis.get("cost_performance") or []
    if cp:
        lines += [
            "| run | acc | USD total | USD/item | acc/USD | tps mean |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for row in cp:
            lines.append(
                f"| {row.get('label')} | {row.get('accuracy')} | {row.get('usd_total')} | "
                f"{row.get('usd_per_item')} | {row.get('acc_per_usd')} | {row.get('tokens_per_sec_mean')} |"
            )
    else:
        lines.append("_Set `cost_per_1m_input_tokens` / `cost_per_1m_output_tokens` in YAML to estimate USD._")

    lines.append("")
    return "\n".join(lines)


def write_benchmark_report(specs: list[str], out: Path) -> Path:
    analysis = analyze_runs(specs)
    if out.suffix == ".md":
        md_path = out
        md_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        out.mkdir(parents=True, exist_ok=True)
        md_path = out / "benchmark.md"
    md_path.write_text(render_benchmark_report(analysis), encoding="utf-8")
    json_path = md_path.with_suffix(".json")
    json_path.write_text(json.dumps(analysis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return md_path
