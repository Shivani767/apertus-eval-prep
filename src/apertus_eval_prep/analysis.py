"""Derived research metrics: thinking, multilingual, robustness, cost, quant, Pareto, OFAT."""

from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any

from apertus_eval_prep.stats import kendall_tau_b, mcnemar, wilson_interval


def thinking_comparison(
    non_thinking: dict[str, Any],
    thinking: dict[str, Any],
) -> dict[str, Any]:
    """Compare paired thinking vs non-thinking runs on the same model."""
    nt_acc = (non_thinking.get("tasks") or {}).get("overall", {}).get("accuracy")
    th_acc = (thinking.get("tasks") or {}).get("overall", {}).get("accuracy")
    nt_lat = non_thinking.get("latency") or {}
    th_lat = thinking.get("latency") or {}
    nt_items = non_thinking.get("items") or []
    th_items = thinking.get("items") or []
    nt_tok = sum(int(r.get("num_new_tokens") or 0) for r in nt_items)
    th_tok = sum(int(r.get("num_new_tokens") or 0) for r in th_items)
    n = len(nt_items) or len(th_items) or 1
    additional = th_tok - nt_tok
    gain = None if nt_acc is None or th_acc is None else round(th_acc - nt_acc, 4)
    efficiency = None
    if gain is not None and additional > 0:
        efficiency = round(gain / additional, 8)
    paired = _paired_correctness(nt_items, th_items)
    mcn = mcnemar(paired["a"], paired["b"]) if paired["a"] else None
    return {
        "non_thinking_accuracy": nt_acc,
        "thinking_accuracy": th_acc,
        "reasoning_gain": gain,
        "reasoning_gain_pp": round(gain * 100, 2) if gain is not None else None,
        "non_thinking_tokens": nt_tok,
        "thinking_tokens": th_tok,
        "additional_tokens": additional,
        "additional_tokens_per_item": round(additional / n, 2),
        "reasoning_efficiency": efficiency,
        "ttft_ms_mean_delta": _delta(th_lat.get("ttft_ms_mean"), nt_lat.get("ttft_ms_mean")),
        "tokens_per_sec_mean_delta": _delta(th_lat.get("tokens_per_sec_mean"), nt_lat.get("tokens_per_sec_mean")),
        "mcnemar": mcn,
    }


def multilingual_analysis(language_block: dict[str, Any]) -> dict[str, Any]:
    """Per-language stats with English baseline and cross-language variance."""
    if not language_block:
        return {}
    accs = {lang: (block.get("accuracy") or 0.0) for lang, block in language_block.items()}
    en = accs.get("en")
    values = list(accs.values())
    worst_lang = min(accs, key=accs.get) if accs else None
    return {
        "per_language_accuracy": accs,
        "english_baseline": en,
        "worst_language": worst_lang,
        "worst_language_accuracy": accs.get(worst_lang) if worst_lang else None,
        "language_performance_gap": round(en - accs[worst_lang], 4) if en is not None and worst_lang else None,
        "cross_language_variance": round(pstdev(values), 6) if len(values) > 1 else 0.0,
        "cross_language_mean": round(mean(values), 4) if values else None,
    }


def paraphrase_robustness(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate accuracy across paraphrase variants for one model."""
    accs = []
    for run in runs:
        acc = (run.get("tasks") or {}).get("overall", {}).get("accuracy")
        if acc is not None:
            accs.append(float(acc))
    if not accs:
        return {}
    mu = mean(accs)
    sd = pstdev(accs) if len(accs) > 1 else 0.0
    # Higher is more robust: 1 - normalized spread (0 when identical, lower when volatile).
    spread = sd / mu if mu > 0 else 0.0
    score = round(max(0.0, 1.0 - spread), 4)
    return {
        "n_variants": len(accs),
        "mean_accuracy": round(mu, 4),
        "std_accuracy": round(sd, 4),
        "best_case": round(max(accs), 4),
        "worst_case": round(min(accs), 4),
        "robustness_score": score,
    }


def cost_performance_metrics(run: dict[str, Any]) -> dict[str, Any]:
    """Derived efficiency metrics; labels estimated vs measured."""
    overall = (run.get("tasks") or {}).get("overall") or {}
    acc = overall.get("accuracy")
    lat = run.get("latency") or {}
    cost = run.get("cost") or {}
    tps = lat.get("tokens_per_sec_mean")
    e2e = lat.get("e2e_ms_mean")
    out: dict[str, Any] = {
        "accuracy": acc,
        "tokens_per_sec_mean": tps,
        "e2e_ms_mean": e2e,
    }
    if cost.get("usd_total") is not None and acc is not None and cost["usd_total"] > 0:
        out["accuracy_per_cost_estimated"] = round(acc / cost["usd_total"], 4)
        out["cost_basis"] = "estimated_from_yaml_pricing"
    if e2e and e2e > 0 and acc is not None:
        out["accuracy_per_second_measured"] = round(acc / (e2e / 1000.0), 6)
        out["latency_basis"] = "measured_e2e_ms_mean"
    return out


def quantization_comparison(
    fp16: dict[str, Any],
    quant: dict[str, Any],
    *,
    quant_label: str,
) -> dict[str, Any]:
    """Delta metrics between fp16 control and quantized run (same model)."""
    fp_acc = (fp16.get("tasks") or {}).get("overall", {}).get("accuracy")
    q_acc = (quant.get("tasks") or {}).get("overall", {}).get("accuracy")
    fp_lat = fp16.get("latency") or {}
    q_lat = quant.get("latency") or {}
    delta = None if fp_acc is None or q_acc is None else round(q_acc - fp_acc, 4)
    fp_tps = fp_lat.get("tokens_per_sec_mean")
    q_tps = q_lat.get("tokens_per_sec_mean")
    tps_change = None
    if fp_tps and q_tps and fp_tps > 0:
        tps_change = round((q_tps - fp_tps) / fp_tps, 4)
    paired = _paired_correctness(fp16.get("items") or [], quant.get("items") or [])
    mcn = mcnemar(paired["a"], paired["b"]) if paired["a"] else None
    return {
        "quantization": quant_label,
        "fp16_accuracy": fp_acc,
        "quant_accuracy": q_acc,
        "accuracy_delta": delta,
        "accuracy_delta_pp": round(delta * 100, 2) if delta is not None else None,
        "fp16_tokens_per_sec": fp_tps,
        "quant_tokens_per_sec": q_tps,
        "throughput_change_ratio": tps_change,
        "mcnemar_vs_fp16": mcn,
        "memory_reduction": None,
        "memory_note": "GPU memory not instrumented in this harness",
    }


def ofat_delta(control: dict[str, Any], treatment: dict[str, Any]) -> dict[str, Any]:
    """Baseline vs treatment delta with Wilson CIs and McNemar where paired."""
    c_over = (control.get("tasks") or {}).get("overall") or {}
    t_over = (treatment.get("tasks") or {}).get("overall") or {}
    c_acc, t_acc = c_over.get("accuracy"), t_over.get("accuracy")
    delta = None if c_acc is None or t_acc is None else round(t_acc - c_acc, 4)
    paired = _paired_correctness(control.get("items") or [], treatment.get("items") or [])
    mcn = mcnemar(paired["a"], paired["b"]) if paired["a"] else None
    return {
        "control_accuracy": c_acc,
        "control_ci95": c_over.get("accuracy_ci95"),
        "treatment_accuracy": t_acc,
        "treatment_ci95": t_over.get("accuracy_ci95"),
        "delta": delta,
        "delta_pp": round(delta * 100, 2) if delta is not None else None,
        "mcnemar": mcn,
    }


def pareto_frontier(
    points: list[dict[str, Any]],
    *,
    maximize: list[str],
    minimize: list[str],
) -> dict[str, Any]:
    """Non-dominated configurations. Each point needs `label` and metric keys."""
    if not points:
        return {"frontier": [], "dominated": []}

    def dominates(a: dict[str, Any], b: dict[str, Any]) -> bool:
        better_or_equal = True
        strictly_better = False
        for key in maximize:
            va, vb = a.get(key), b.get(key)
            if va is None or vb is None:
                return False
            if va < vb:
                better_or_equal = False
            if va > vb:
                strictly_better = True
        for key in minimize:
            va, vb = a.get(key), b.get(key)
            if va is None or vb is None:
                return False
            if va > vb:
                better_or_equal = False
            if va < vb:
                strictly_better = True
        return better_or_equal and strictly_better

    frontier: list[dict[str, Any]] = []
    dominated: list[str] = []
    for i, p in enumerate(points):
        label = p.get("label", str(i))
        if any(dominates(other, p) for j, other in enumerate(points) if j != i):
            dominated.append(str(label))
        else:
            frontier.append(p)
    return {"frontier": frontier, "dominated": dominated}


def build_pareto_from_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Standard accuracy↑ cost↓ latency↓ Pareto from scored JSON blobs."""
    points = []
    for run in runs:
        settings = (run.get("manifest") or {}).get("settings") or {}
        label = settings.get("run_id") or settings.get("model_id") or "run"
        eff = cost_performance_metrics(run)
        cost_obj = run.get("cost") or {}
        points.append(
            {
                "label": label,
                "model_id": settings.get("model_id"),
                "accuracy": eff.get("accuracy"),
                "usd_total_estimated": cost_obj.get("usd_total"),
                "e2e_ms_mean": eff.get("e2e_ms_mean"),
            }
        )
    has_cost = any(p.get("usd_total_estimated") is not None for p in points)
    minimize = ["e2e_ms_mean"]
    if has_cost:
        minimize.append("usd_total_estimated")
    return pareto_frontier(points, maximize=["accuracy"], minimize=minimize)


def _delta(a: Any, b: Any) -> float | None:
    if a is None or b is None:
        return None
    return round(float(a) - float(b), 4)


def _paired_correctness(
    items_a: list[dict[str, Any]],
    items_b: list[dict[str, Any]],
) -> dict[str, list[bool]]:
    map_a = {r["id"]: bool(r.get("correct")) for r in items_a if r.get("id")}
    map_b = {r["id"]: bool(r.get("correct")) for r in items_b if r.get("id")}
    ids = sorted(set(map_a) & set(map_b))
    if not ids:
        return {"a": [], "b": []}
    return {"a": [map_a[i] for i in ids], "b": [map_b[i] for i in ids]}
