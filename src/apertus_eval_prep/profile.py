"""Runtime/tokenizer profiling from scored run artifacts.

Every number here is derived from MEASURED per-item records (e2e_ms,
ttft_ms, tokens_per_sec, num_new_tokens, prompt_tokens) in a committed run
JSON. Items missing a timing field are excluded from that field's stats and
counted in n_missing_<field> — never zero-filled. Generation speed is a
runtime property of the stack (backend/quantization/hardware), not a model
quality property; use it to contextualize accuracy, not to rank models.
"""

from __future__ import annotations

from statistics import mean, median
from typing import Any


def _stat(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "median": None, "n": 0}
    return {
        "mean": round(mean(values), 4),
        "median": round(median(values), 4),
        "n": len(values),
    }


def _group_profile(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate measured runtime fields for one group of items.

    e2e_ms == 0.0 entries are backend placeholders (the committed vLLM run
    records 0.0 while ttft/tps are None): they are counted in
    n_e2e_zero_placeholder and EXCLUDED from e2e statistics — a zero here
    means "not measured", never "instant".
    """
    tps = [it["tokens_per_sec"] for it in items if it.get("tokens_per_sec")]
    e2e_raw = [it.get("e2e_ms") for it in items]
    e2e_zero = sum(1 for v in e2e_raw if v == 0.0)
    e2e = [v for v in e2e_raw if v]
    ttft = [it["ttft_ms"] for it in items if it.get("ttft_ms")]
    new_tok = [it["num_new_tokens"] for it in items if it.get("num_new_tokens")]
    prompt_tok = [it["prompt_tokens"] for it in items if it.get("prompt_tokens")]
    correct = [it for it in items if it.get("correct")]
    n = len(items)
    out = {
        "n_items": n,
        "n_correct": len(correct),
        "accuracy": round(len(correct) / n, 6) if n else None,
        "tokens_per_sec": _stat(tps),
        "e2e_ms": _stat(e2e),
        "n_e2e_zero_placeholder": e2e_zero,
        "ttft_ms": _stat(ttft),
        "num_new_tokens": _stat(new_tok),
        "prompt_tokens": _stat(prompt_tok),
    }
    return out


def runtime_profile(blob: dict[str, Any]) -> dict[str, Any]:
    """Per-task and per-language runtime/quality profile of one run."""
    items = blob.get("items") or []
    manifest = blob.get("manifest") or {}
    settings = manifest.get("settings") or {}

    by_task: dict[str, dict[str, Any]] = {}
    by_lang: dict[str, dict[str, Any]] = {}
    for it in items:
        by_task.setdefault(it.get("task") or "unknown", []).append(it)
        by_lang.setdefault(it.get("language") or "unknown", []).append(it)

    return {
        "model_id": settings.get("model_id") or blob.get("model_id"),
        "backend": settings.get("backend"),
        "quantization": settings.get("quantization"),
        "hardware": manifest.get("hardware"),
        "overall": _group_profile(items),
        "by_task": {t: _group_profile(g) for t, g in sorted(by_task.items())},
        "by_language": {l: _group_profile(g) for l, g in sorted(by_lang.items())},
        "provenance": "DERIVED from measured per-item timing records",
    }


def render_profile_markdown(prof: dict[str, Any]) -> str:
    def fmt(s: dict[str, float | None]) -> str:
        if s["mean"] is None:
            return "n/a"
        return f"{s['mean']} (med {s['median']}, n={s['n']})"

    lines = [
        "# Runtime profile: "
        f"{prof.get('model_id')} / {prof.get('backend')} / "
        f"{prof.get('quantization')} / {prof.get('hardware')}",
        "",
        f"Overall: n={prof['overall']['n_items']}, "
        f"acc={prof['overall']['accuracy']}, "
        f"tok/s mean={fmt(prof['overall']['tokens_per_sec'])}",
        "",
        "## By task",
        "",
        "| task | n | acc | tok/s mean | e2e ms mean | ttft ms mean | new tok mean |",
        "|---|---|---|---|---|---|---|",
    ]
    for t, p in prof["by_task"].items():
        lines.append(
            f"| {t} | {p['n_items']} | {p['accuracy']} | "
            f"{p['tokens_per_sec']['mean']} | {p['e2e_ms']['mean']} | "
            f"{p['ttft_ms']['mean']} | {p['num_new_tokens']['mean']} |"
        )
    lines += [
        "",
        "## By language",
        "",
        "| language | n | acc | tok/s mean |",
        "|---|---|---|---|",
    ]
    for l, p in prof["by_language"].items():
        lines.append(
            f"| {l} | {p['n_items']} | {p['accuracy']} | "
            f"{p['tokens_per_sec']['mean']} |"
        )
    lines += [
        "",
        "Timing fields absent from an item are excluded from that statistic "
        "(counts in the JSON under n=0 entries); nothing is zero-filled. "
        "tok/s reflects the full stack, not the model alone.",
        "",
        f"_Provenance: {prof['provenance']}_",
    ]
    return "\n".join(lines) + "\n"