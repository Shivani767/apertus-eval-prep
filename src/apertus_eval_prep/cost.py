"""Evaluation cost tracking (Phase 10).

Infrastructure for the research question "how much evaluation is enough?".
Records what was ACTUALLY measured about evaluation cost, distinguishes
MEASURED / DERIVED / UNAVAILABLE, and never invents or zero-fills missing
cost numbers.

Grounded in what the harness currently records per run (results/runs/*.json):

    latency: {n, ttft_ms_mean, ttft_ms_p50, ttft_ms_p95,
              e2e_ms_mean, e2e_ms_p95, tokens_per_sec_mean}

Known limitation discovered by inspection: some backends record 0.0 for
e2e/ttft when timing is unavailable (e.g. the committed vLLM cell
``Phi-3.5-mini-instruct_backend_vllm_e796a0ecee505133.json``). 0.0 ms for
800 model calls is not a physical measurement; the cost model therefore
treats non-positive or None timings as UNAVAILABLE (raw value preserved),
never as zero cost.

Monetary cost, memory, and hardware energy are NOT recorded anywhere by the
current harness and are intentionally absent: there is no reliable source
for them yet.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from apertus_eval_prep.result_schema import DERIVED, MEASURED, UNAVAILABLE

#: Latency fields the harness records per run, all in the ``latency`` block.
LATENCY_FIELDS = ("ttft_ms_mean", "e2e_ms_mean", "tokens_per_sec_mean")


@dataclass
class CostRecord:
    """Cost facts for one run, with per-field quality labels.

    quality maps each field name to MEASURED, DERIVED, or UNAVAILABLE.
    ``raw`` preserves the original latency values (including 0.0 / None
    placeholders) so nothing is silently rewritten.
    """

    run_id: str | None = None
    n_calls: int | None = None
    ttft_ms_mean: float | None = None
    e2e_ms_mean: float | None = None
    tokens_per_sec_mean: float | None = None
    est_total_s: float | None = None
    quality: dict[str, str] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "n_calls": self.n_calls,
            "ttft_ms_mean": self.ttft_ms_mean,
            "e2e_ms_mean": self.e2e_ms_mean,
            "tokens_per_sec_mean": self.tokens_per_sec_mean,
            "est_total_s": self.est_total_s,
            "quality": dict(self.quality),
        }


def _measured_number(value: Any) -> float | None:
    """Positive finite number -> float; anything else -> None.

    None / non-numeric / NaN / inf / <= 0 are all treated as not measured.
    """
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f if f > 0.0 else None

def extract_cost(result: Mapping[str, Any], run_id: str | None = None) -> CostRecord:
    """Build a CostRecord from one run-result dict (real or synthetic).

    est_total_s is DERIVED as e2e_ms_mean * n_calls / 1000 and exists only
    where both inputs are measured; it is an estimate of serial wall-clock
    time, not a stopwatch measurement.
    """
    lat = result.get("latency") or {}
    n = lat.get("n")
    n_calls = None
    if (isinstance(n, (int, float)) and not isinstance(n, bool)
            and n > 0 and float(n).is_integer()):
        n_calls = int(n)

    values: dict[str, float | None] = {}
    quality: dict[str, str] = {}
    for fname in LATENCY_FIELDS:
        values[fname] = _measured_number(lat.get(fname))
        quality[fname] = MEASURED if values[fname] is not None else UNAVAILABLE
    quality["n_calls"] = MEASURED if n_calls is not None else UNAVAILABLE

    est = None
    if values["e2e_ms_mean"] is not None and n_calls is not None:
        est = values["e2e_ms_mean"] * n_calls / 1000.0
        quality["est_total_s"] = DERIVED
    else:
        quality["est_total_s"] = UNAVAILABLE

    return CostRecord(
        run_id=run_id or result.get("run_id"),
        n_calls=n_calls,
        ttft_ms_mean=values["ttft_ms_mean"],
        e2e_ms_mean=values["e2e_ms_mean"],
        tokens_per_sec_mean=values["tokens_per_sec_mean"],
        est_total_s=est,
        quality=quality,
        raw={fname: lat.get(fname) for fname in LATENCY_FIELDS},
    )


def cost_from_run_file(path: str) -> CostRecord:
    """Extract cost facts from a committed run-result JSON file."""
    with open(path, encoding="utf-8") as fh:
        return extract_cost(json.load(fh))


def summarize_costs(records: list[CostRecord]) -> dict[str, Any]:
    """Coverage summary over records. Missing fields are counted, never zero-filled."""
    total = len(records)
    fields: dict[str, Any] = {}
    for fname in ("n_calls", *LATENCY_FIELDS, "est_total_s"):
        have = sum(1 for r in records if getattr(r, fname) is not None)
        fields[fname] = {
            "n_available": have,
            "n_total": total,
            "measured_fraction": round(have / total, 4) if total else None,
        }
    totals = [r.est_total_s for r in records if r.est_total_s is not None]
    return {
        "n_runs": total,
        "fields": fields,
        "est_total_s": {
            "n": len(totals),
            "sum": round(sum(totals), 3) if totals else None,
            "note": "DERIVED from e2e_ms_mean * n_calls; sums only measured inputs",
        },
    }


def budget_curve(observations: list[tuple[float, float]]) -> list[dict[str, float]]:
    """Cost-vs-confidence points, sorted by ascending cost.

    ``observations`` are (cost, confidence) pairs that the CALLER measured
    (e.g. cumulative wall-clock vs selecting_confidence from Phase 9 while
    replaying a real run). No real observation set exists yet in this repo;
    tests use synthetic pairs. Analysis of the curve is deliberately left to
    the caller until real data exists.
    """
    points: list[dict[str, float]] = []
    for cost, conf in observations:
        c, k = float(cost), float(conf)
        if c < 0 or math.isnan(c):
            raise ValueError(f"cost must be a finite number >= 0, got {cost!r}")
        if not (0.0 <= k <= 1.0):
            raise ValueError(f"confidence must be in [0, 1], got {conf!r}")
        points.append({"cost": c, "confidence": k})
    points.sort(key=lambda p: p["cost"])
    return points
