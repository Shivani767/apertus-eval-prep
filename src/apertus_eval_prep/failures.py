"""Failure taxonomy: classify per-item outcomes from scored run JSONs.

Categories (mutually exclusive, checked in this order):
1. runtime_error   — item carries an `error` field (generation failed).
2. empty_output    — generation is empty/whitespace.
3. unparseable     — generation produced text but no answer could be
                     extracted (predicted is None).
4. wrong_answer    — an answer was extracted but disagrees with gold.
5. correct         — extracted answer matches gold.

Every category is reported with its measured count and rate; a category with
zero occurrences is a measured zero (the current committed control runs have
no runtime errors, empty outputs, or unparseable items — all failures are
wrong_answer). The taxonomy never re-judges correctness; it reuses the
stored `correct` / `predicted` / `gold` fields verbatim.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CATEGORIES = ("runtime_error", "empty_output", "unparseable", "wrong_answer", "correct")


def classify_item(item: dict[str, Any]) -> str:
    if item.get("error") is not None:
        return "runtime_error"
    gen = item.get("generation")
    if gen is None or not str(gen).strip():
        return "empty_output"
    if item.get("predicted") is None:
        return "unparseable"
    return "correct" if item.get("correct") else "wrong_answer"


def failure_taxonomy(blob: dict[str, Any]) -> dict[str, Any]:
    """Aggregate per-item categories over one scored run blob.

    Reports overall counts/rates and a per-task breakdown. Rates are over
    ALL items in scope (so category rates sum to 1). A missing `items`
    list yields total=0 with every category at 0 — never fabricated.
    """
    items = blob.get("items") or []
    total = len(items)
    counts = {c: 0 for c in CATEGORIES}
    per_task: dict[str, dict[str, Any]] = {}
    for it in items:
        cat = classify_item(it)
        counts[cat] += 1
        task = str(it.get("task", "unknown"))
        bucket = per_task.setdefault(
            task, {"total": 0, **{c: 0 for c in CATEGORIES}}
        )
        bucket["total"] += 1
        bucket[cat] += 1
    for bucket in per_task.values():
        bucket["rates"] = {
            c: (bucket[c] / bucket["total"] if bucket["total"] else None)
            for c in CATEGORIES
        }
    return {
        "total": total,
        "counts": counts,
        "rates": {c: (counts[c] / total if total else None) for c in CATEGORIES},
        "per_task": per_task,
        "failure_rate": (1 - counts["correct"] / total) if total else None,
    }


def load_blob(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def render_failure_markdown(reports: dict[str, dict[str, Any]]) -> str:
    lines = [
        "# Failure taxonomy report",
        "",
        "Categories are mutually exclusive; rates are over all items in scope.",
        "A zero count is a measured zero, not a missing value.",
        "",
    ]
    for label, rep in sorted(reports.items()):
        lines.append(f"## {label}")
        lines.append("")
        lines.append(f"- items: {rep['total']}, overall failure rate: "
                     f"{rep['failure_rate'] if rep['failure_rate'] is not None else 'None (no items)'}")
        lines.append("")
        lines.append("| category | count | rate |")
        lines.append("|---|---|---|")
        for c in CATEGORIES:
            rate = rep["rates"][c]
            lines.append(
                f"| {c} | {rep['counts'][c]} | "
                f"{'—' if rate is None else format(rate, '.4f')} |"
            )
        lines.append("")
        if rep["per_task"]:
            lines.append("| task | total | wrong_answer | unparseable | empty_output | runtime_error |")
            lines.append("|---|---|---|---|---|---|")
            for task, b in sorted(rep["per_task"].items()):
                lines.append(
                    f"| {task} | {b['total']} | {b['wrong_answer']} "
                    f"| {b['unparseable']} | {b['empty_output']} | {b['runtime_error']} |"
                )
        lines.append("")
    return "\n".join(lines)