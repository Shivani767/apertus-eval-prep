"""Deterministic, privacy-safe sampling from immutable run artifacts."""
from __future__ import annotations

import random
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from apertus_eval_prep.core.artifacts import FAILURES, RAW_OUTPUTS, SCORED_EXAMPLES, load_run_manifest
from apertus_eval_prep.release.failures import normalize_failure_records
from apertus_eval_prep.utils.pii import redact_for_artifact
from apertus_eval_prep.utils.serialization import read_jsonl, read_yaml

SAMPLING_STRATEGIES = ("random", "stratified", "priority")


def _item_id(row: Mapping[str, Any]) -> str:
    return str(row.get("example_id") or row.get("episode_id") or row.get("test_id") or "unknown")


def _baseline_scores(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return {
        _item_id(row): row.get("score")
        for row in read_jsonl(Path(path) / SCORED_EXAMPLES) if isinstance(row, Mapping)
    }


def _text(value: Any, fallback: Any = "") -> Any:
    if isinstance(value, Mapping):
        return value.get("text", value.get("prompt", fallback))
    return value if value is not None else fallback


def _raw_rows(run_dir: Path) -> dict[str, dict[str, Any]]:
    config_path = run_dir / "config.resolved.yaml"
    if not config_path.exists():
        return {}
    try:
        reporting = read_yaml(config_path).get("reporting") or {}
    except (TypeError, ValueError):
        return {}
    if not reporting.get("include_raw_outputs", False):
        return {}
    return {
        _item_id(row): row for row in read_jsonl(run_dir / RAW_OUTPUTS)
        if isinstance(row, Mapping)
    }


def sample_review_candidates(
    run_dir: str | Path, *, sample_size: int = 50, strategy: str = "stratified",
    seed: int = 0, baseline_run: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Sample scored examples without reading raw content when retention is disabled."""
    if strategy not in SAMPLING_STRATEGIES:
        raise ValueError(f"sampling strategy must be one of {SAMPLING_STRATEGIES}")
    if sample_size < 0:
        raise ValueError("sample_size must be >= 0")
    directory = Path(run_dir)
    manifest = load_run_manifest(directory)
    raw = _raw_rows(directory)
    failure_map = {
        _item_id(row): row
        for row in normalize_failure_records(read_jsonl(directory / FAILURES), manifest=manifest)
    }
    baseline = _baseline_scores(baseline_run)
    candidates: list[dict[str, Any]] = []
    for row in read_jsonl(directory / SCORED_EXAMPLES):
        if not isinstance(row, Mapping):
            continue
        item_id = _item_id(row)
        failure = failure_map.get(item_id, {})
        observation = raw.get(item_id, {})
        request = observation.get("request") if isinstance(observation.get("request"), Mapping) else {}
        response = observation.get("response") if isinstance(observation.get("response"), Mapping) else observation
        labels = {str(x) for x in failure.get("condition_labels", [])}
        item = {
            "item_id": item_id, "run_id": str(manifest.get("run_id") or ""), "example_id": row.get("example_id"), "episode_id": row.get("episode_id"),
            "task": row.get("task") or failure.get("task"), "domain": row.get("domain") or failure.get("domain"),
            "language": row.get("language") or failure.get("language"),
            "sanitized_prompt": _text(request.get("prompt"), failure.get("sanitized_input_excerpt", "[RAW_RETENTION_DISABLED]")),
            "sanitized_context": _text(request.get("context"), ""), "sanitized_output": _text(response.get("text"), "[RAW_RETENTION_DISABLED]"),
            "passed": bool(row.get("correct")),
            "safety_critical": failure.get("severity") in {"high", "critical"},
            "condition_sensitive": any("sensitive" in label for label in labels),
            "baseline_disagreement": item_id in baseline and baseline[item_id] != row.get("score"),
            "evidence_mode": (manifest.get("evidence") or {}).get("mode", manifest.get("evidence_mode", "UNKNOWN")),
        }
        candidates.append(redact_for_artifact(item))
    rng = random.Random(seed)
    for item in candidates:
        item["_priority"] = (
            int(item["safety_critical"]) * 8 + int(item["condition_sensitive"]) * 4
            + int(item["baseline_disagreement"]) * 2 + int(not item["passed"]) + rng.random() / 1000
        )
    if strategy == "random":
        rng.shuffle(candidates)
        selected = candidates[:sample_size]
        for item in selected:
            item.pop("_priority", None)
        return selected
    if strategy == "priority":
        candidates.sort(key=lambda item: item["_priority"], reverse=True)
        selected = candidates[:sample_size]
    else:
        groups = {True: [i for i in candidates if i["passed"]], False: [i for i in candidates if not i["passed"]]}
        selected = []
        for group in groups.values():
            group.sort(key=lambda item: item["_priority"], reverse=True)
            selected.extend(group[: max(1, sample_size // 2)] if group else [])
        remaining = [i for i in candidates if i not in selected]
        remaining.sort(key=lambda item: item["_priority"], reverse=True)
        selected.extend(remaining[: max(0, sample_size - len(selected))])
        selected = selected[:sample_size]
    for item in selected:
        item.pop("_priority", None)
    return selected


__all__ = ["SAMPLING_STRATEGIES", "sample_review_candidates"]
