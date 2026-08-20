from __future__ import annotations

import re
from statistics import mean

from apertus_eval_prep.stats import wilson_interval

MC_TASKS = {"arc_easy", "template_canary", "hellaswag"}
MATH_TASKS = {"gsm8k", "multilingual", "mgsm"}

_NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?")
_LETTER_RE = re.compile(r"\b([ABCD])\b", re.IGNORECASE)
_LETTER_PREFIX = re.compile(r"^\s*\(?([ABCD])\)?", re.IGNORECASE)


def extract_mc_letter(text: str) -> str | None:
    if not text or not text.strip():
        return None
    prefix = _LETTER_PREFIX.match(text.strip())
    if prefix:
        return prefix.group(1).upper()
    found = _LETTER_RE.findall(text)
    if found:
        return found[-1].upper()
    return None


def extract_number(text: str) -> str | None:
    if not text:
        return None
    matches = _NUMBER_RE.findall(text.replace(",", ""))
    if not matches:
        return None
    value = matches[-1].replace(",", ".")
    if value.endswith(".0"):
        value = value[:-2]
    try:
        as_float = float(value)
        if as_float.is_integer():
            return str(int(as_float))
        return str(as_float)
    except ValueError:
        return matches[-1]


def predicted(task: str, generation: str) -> str | None:
    if task in MC_TASKS:
        return extract_mc_letter(generation)
    if task in MATH_TASKS:
        return extract_number(generation)
    return generation.strip() or None


def is_correct(task: str, generation: str, gold: str) -> bool:
    pred = predicted(task, generation)
    if pred is None:
        return False
    return pred.strip().upper() == gold.strip().upper()


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    frac = k - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


def summarize_latency(rows: list[dict]) -> dict:
    ttft = [r["ttft_ms"] for r in rows if r.get("ttft_ms") is not None]
    e2e = [r["e2e_ms"] for r in rows if r.get("e2e_ms") is not None]
    tps = [r["tokens_per_sec"] for r in rows if r.get("tokens_per_sec")]
    return {
        "n": len(rows),
        "ttft_ms_mean": round(mean(ttft), 2) if ttft else None,
        "ttft_ms_p50": round(percentile(ttft, 0.50), 2) if ttft else None,
        "ttft_ms_p95": round(percentile(ttft, 0.95), 2) if ttft else None,
        "e2e_ms_mean": round(mean(e2e), 2) if e2e else None,
        "e2e_ms_p95": round(percentile(e2e, 0.95), 2) if e2e else None,
        "tokens_per_sec_mean": round(mean(tps), 3) if tps else None,
    }


def _task_block(group: list[dict]) -> dict:
    n = len(group)
    correct = sum(1 for r in group if r["correct"])
    lo, hi = wilson_interval(correct, n)
    return {
        "n": n,
        "correct": correct,
        "accuracy": round(correct / n, 4) if n else None,
        "accuracy_ci95": [round(lo, 4), round(hi, 4)] if lo is not None and hi is not None else None,
    }


def summarize_tasks(rows: list[dict]) -> dict:
    by_task: dict[str, list[dict]] = {}
    for row in rows:
        by_task.setdefault(row["task"], []).append(row)
    out = {task: _task_block(group) for task, group in by_task.items()}
    out["overall"] = _task_block(rows)
    return out
