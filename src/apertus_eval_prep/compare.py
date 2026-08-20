from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _acc(blob: dict[str, Any], task: str) -> float | None:
    block = (blob.get("tasks") or {}).get(task) or {}
    return block.get("accuracy")


def _delta(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return round(b - a, 4)


def compare_runs(path_a: Path, path_b: Path) -> dict[str, Any]:
    a = json.loads(path_a.read_text(encoding="utf-8"))
    b = json.loads(path_b.read_text(encoding="utf-8"))
    sa = a["manifest"]["settings"]
    sb = b["manifest"]["settings"]
    keys = [
        "model_id",
        "tokenizer_id",
        "revision",
        "backend",
        "chat_template",
        "max_new_tokens",
        "seed",
        "dtype",
        "quantization",
        "temperature",
        "top_p",
        "prompt_id",
    ]
    setting_diff = {k: {"a": sa.get(k), "b": sb.get(k)} for k in keys if sa.get(k) != sb.get(k)}
    tasks = sorted(set((a.get("tasks") or {}) | (b.get("tasks") or {})))
    task_table = []
    for task in tasks:
        aa, bb = _acc(a, task), _acc(b, task)
        task_table.append({"task": task, "acc_a": aa, "acc_b": bb, "delta_b_minus_a": _delta(aa, bb)})
    lat_a, lat_b = a.get("latency") or {}, b.get("latency") or {}
    return {
        "a": str(path_a),
        "b": str(path_b),
        "setting_diff": setting_diff,
        "comparable_except_listed_settings": True,
        "tasks": task_table,
        "latency": {
            "ttft_ms_p95_a": lat_a.get("ttft_ms_p95"),
            "ttft_ms_p95_b": lat_b.get("ttft_ms_p95"),
            "tokens_per_sec_mean_a": lat_a.get("tokens_per_sec_mean"),
            "tokens_per_sec_mean_b": lat_b.get("tokens_per_sec_mean"),
        },
        "hardware_a": a["manifest"].get("hardware"),
        "hardware_b": b["manifest"].get("hardware"),
        "note": (
            "If more than one setting changed, or hardware/dtype/backend all moved at once, "
            "do not treat the accuracy delta as a pure chat-template or pure-backend effect."
        ),
    }


def to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Eval comparison",
        "",
        f"- A: `{report['a']}`",
        f"- B: `{report['b']}`",
        "",
        "## Settings that differ",
        "",
    ]
    if not report["setting_diff"]:
        lines.append("None. Manifest settings match for the compared keys.")
    else:
        lines.append("| key | A | B |")
        lines.append("|---|---|---|")
        for key, pair in report["setting_diff"].items():
            lines.append(f"| `{key}` | {pair['a']} | {pair['b']} |")
    lines += ["", "## Accuracy", "", "| task | acc A | acc B | delta (B−A) |", "|---|---|---|---|"]
    for row in report["tasks"]:
        lines.append(
            f"| {row['task']} | {row['acc_a']} | {row['acc_b']} | {row['delta_b_minus_a']} |"
        )
    lat = report["latency"]
    lines += [
        "",
        "## Latency",
        "",
        f"- TTFT p95 (ms): A={lat['ttft_ms_p95_a']} B={lat['ttft_ms_p95_b']}",
        f"- tokens/sec mean: A={lat['tokens_per_sec_mean_a']} B={lat['tokens_per_sec_mean_b']}",
        "",
        report["note"],
        "",
    ]
    return "\n".join(lines) + "\n"
