"""Result status model + enriched/validated run view (Phase 1).

Explicit MEASURED / SAMPLED / DERIVED / PENDING / UNAVAILABLE status.
Backwards compatible: run JSON files are never rewritten; enrichment is a
read-time join of (registry row + run blob). Missing data stays None, never 0.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

MEASURED = "MEASURED"
SAMPLED = "SAMPLED"
DERIVED = "DERIVED"
PENDING = "PENDING"
UNAVAILABLE = "UNAVAILABLE"

STATUSES = (MEASURED, SAMPLED, DERIVED, PENDING, UNAVAILABLE)


def classify_row(row: dict[str, Any], blob: dict[str, Any] | None = None) -> str:
    """Status of one registry row.

    MEASURED: registry ok + greedy decode (temperature 0) blob present.
    SAMPLED: registry ok + sampling decode (temperature > 0) blob present.
    PENDING: row missing/unsuccessful, or blob file missing.
    DERIVED/UNAVAILABLE are assigned by callers for computed/missing analyses.
    """
    if row.get("status") != "ok" or blob is None:
        return PENDING
    settings = ((blob.get("manifest") or {}).get("settings")) or {}
    try:
        temp = float(settings.get("temperature", 0.0))
    except (TypeError, ValueError):
        temp = 0.0
    return SAMPLED if temp > 0 else MEASURED


def enrich_run(row: dict[str, Any], blob: dict[str, Any] | None) -> dict[str, Any]:
    """Validated view joining registry metadata + run blob (read-only).

    Keys: run_id, status, experiment_id, timestamp, model, task, protocol,
    runtime, metric, provenance, notes. Unknown fields are None, never invented.
    """
    manifest = (blob or {}).get("manifest") or {}
    settings = manifest.get("settings") or {}
    packages = manifest.get("packages") or {}
    hardware = manifest.get("hardware") or dict(row.get("hardware") or {})
    tasks = (blob or {}).get("tasks") or {}
    overall = tasks.get("overall") or row.get("overall") or {}
    backend = settings.get("backend")
    return {
        "run_id": row.get("run_id") or settings.get("run_id"),
        "status": classify_row(row, blob),
        "experiment_id": row.get("experiment_id") or settings.get("experiment_id"),
        "timestamp": manifest.get("utc") or row.get("utc"),
        "model": {
            "model_id": row.get("model_id") or settings.get("model_id"),
            "model_revision": settings.get("revision"),
            "tokenizer_id": settings.get("tokenizer_id"),
        },
        "task": {
            "tasks": list(settings.get("tasks") or []),
            "dataset_path": settings.get("data_path"),
            "dataset_revision": settings.get("dataset_revision"),
            "n": overall.get("n"),
        },
        "protocol": {
            "prompt_id": settings.get("prompt_id"),
            "prompt_family": settings.get("prompt_family"),
            "prompt_version": settings.get("prompt_version"),
            "fewshot_path": settings.get("fewshot_path"),
            "paraphrase_id": settings.get("paraphrase_id"),
            "thinking_mode": settings.get("thinking_mode"),
            "temperature": settings.get("temperature"),
            "top_p": settings.get("top_p"),
            "seed": settings.get("seed"),
            "max_new_tokens": settings.get("max_new_tokens"),
            "chat_template": settings.get("chat_template"),
            "backend": backend,
            "backend_version": packages.get("vllm")
            if backend == "vllm"
            else packages.get("transformers"),
            "quantization": settings.get("quantization"),
            "dtype": settings.get("dtype"),
            "factor": row.get("factor") or (blob or {}).get("factor"),
            "factor_level": row.get("factor_level") or (blob or {}).get("factor_level"),
        },
        "runtime": {
            "hardware": hardware,
            "software": packages,
            "git_commit": manifest.get("git_commit") or row.get("git_commit"),
            "git_dirty": manifest.get("git_dirty"),
            "device": settings.get("device"),
        },
        "metric": {
            "metric": "accuracy",
            "metric_value": overall.get("accuracy"),
            "correct": overall.get("correct"),
            "n": overall.get("n"),
            "confidence_interval": overall.get("accuracy_ci95"),
            "per_task": {
                k: v for k, v in tasks.items() if k != "overall" and isinstance(v, dict)
            },
            "latency": (blob or {}).get("latency") or {},
            "cost": (blob or {}).get("cost"),
        },
        "provenance": {
            "artifact_path": row.get("path"),
            "config_hash": row.get("config_hash") or (blob or {}).get("config_hash"),
        },
        "notes": {
            "missing_revisions": ["revision"] if settings.get("revision") is None else None,
            "incomparability": (blob or {}).get("incomparability"),
        },
    }

def validate_enriched(view: dict[str, Any]) -> list[str]:
    """Problems with a view; empty means structurally valid.

    MEASURED/SAMPLED require run_id, model_id, metric n/value, artifact path.
    PENDING rows only require run identity (they document absence, not scores).
    """
    problems: list[str] = []
    status = view.get("status")
    if status not in STATUSES:
        return [f"status {status!r} not in {list(STATUSES)}"]
    if not view.get("run_id"):
        problems.append("missing run_id")
    if not (view.get("model") or {}).get("model_id"):
        problems.append("missing model.model_id")
    if status in (MEASURED, SAMPLED):
        metric = view.get("metric") or {}
        if metric.get("n") is None:
            problems.append("missing metric.n")
        if metric.get("metric_value") is None:
            problems.append("missing metric.metric_value")
        if not (view.get("provenance") or {}).get("artifact_path"):
            problems.append("missing provenance.artifact_path")
    return problems


def load_enriched_registry(
    registry_path: Path, repo_root: Path | None = None
) -> list[dict[str, Any]]:
    """Registry JSONL + run blobs joined into enriched views (read-only).

    Missing blob files become PENDING views (no score invented). Malformed JSON
    lines raise, so corruption is loud rather than silently skipped.
    """
    import json  # noqa: F401  (kept explicit: this join reads JSON blobs)

    from apertus_eval_prep.registry import load_registry
    from apertus_eval_prep.report import load_run

    root = repo_root or registry_path.parent.parent
    views: list[dict[str, Any]] = []
    for row in load_registry(registry_path):
        blob: dict[str, Any] | None = None
        rel = row.get("path")
        if row.get("status") == "ok" and rel:
            p = Path(rel)
            if not p.is_absolute():
                p = root / p
            if p.exists():
                blob = load_run(p)
        views.append(enrich_run(row, blob))
    return views


def coverage(views: list[dict[str, Any]]) -> dict[str, Any]:
    """Count views by status; MEASURED/SAMPLED are evidence, PENDING is absence."""
    counts = {s: 0 for s in STATUSES}
    for v in views:
        counts[v.get("status", PENDING)] = counts.get(v.get("status"), 0) + 1
    return {
        "total": len(views),
        "by_status": counts,
        "evidence": counts[MEASURED] + counts[SAMPLED],
    }
