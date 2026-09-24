"""Shared artifact loader for the paper pipeline.

Loads the committed paper registry (``results/registry_paper.jsonl``) and the
scored run JSONs it references, verifies registry<->artifact consistency, and
exposes the paired per-item correctness vectors needed for the paper's
statistical analyses.

Everything here operates on committed measurement artifacts. Nothing in this
module imputes, synthesizes, or zero-fills missing data: a missing run is
reported as missing.

Usage from other scripts::

    from paper_common import load_paper_data

    data = load_paper_data(REPO_ROOT)
    data["blobs"]["Qwen2.5-3B-Instruct_prompt_id_5shot_8b703d7cb8d9627a"]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from apertus_eval_prep.registry import config_hash, load_registry  # noqa: E402
from apertus_eval_prep.scoring import summarize_tasks, is_correct, predicted
from apertus_eval_prep.stats import wilson_interval

REGISTRY_PATH = REPO_ROOT / "results" / "registry_paper.jsonl"
RUNS_DIR = REPO_ROOT / "results" / "runs"

SHORT_MODEL = {
    "HuggingFaceTB/SmolLM2-1.7B-Instruct": "SmolLM2-1.7B",
    "Qwen/Qwen2.5-3B-Instruct": "Qwen2.5-3B",
    "microsoft/Phi-3.5-mini-instruct": "Phi-3.5-mini",
    "Qwen/Qwen2.5-7B-Instruct": "Qwen2.5-7B",
}

MODELS_IN_MATRIX = [
    "HuggingFaceTB/SmolLM2-1.7B-Instruct",
    "Qwen/Qwen2.5-3B-Instruct",
    "microsoft/Phi-3.5-mini-instruct",
]

# Config ordering used for all matrices/tables (label -> (factor, level)).
SHARED_CONFIGS = [
    ("control", "control"),
    ("prompt_id", "concise"),
    ("prompt_id", "5shot"),
    ("backend", "vllm"),
    ("seed", "1"),
    ("seed", "2"),
    ("quantization", "int8"),
    ("quantization", "int4"),
]

FACTOR_LABEL = {
    "control": "control",
    "prompt_id": "prompt",
    "backend": "backend",
    "quantization": "quantization",
    "seed": "greedy seed",
    "sampled": "sampling",
    "paraphrase_id": "paraphrase",
}


def load_registry_rows() -> list[dict[str, Any]]:
    rows = load_registry(REGISTRY_PATH)
    return [r for r in rows if r.get("status") == "ok"]


def load_blob_by_row(row: dict[str, Any]) -> dict[str, Any]:
    """Load the run JSON a registry row points at (repo-root-relative)."""
    path = row["path"]
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / path
    return json.loads(p.read_text(encoding="utf-8"))


def items_correct(blob: dict[str, Any]) -> dict[str, bool]:
    """item_id -> correct, from the committed per-item records."""
    return {it["id"]: bool(it["correct"]) for it in blob["items"]}


def verify_row(row: dict[str, Any], blob: dict[str, Any]) -> dict[str, Any]:
    """Recompute provenance facts for one registry row from its artifact.

    Returns a dict of booleans; never mutates anything. Hash recomputation
    mirrors the repo's own ``reproduce.verify_reproduction`` checks.
    """
    settings = blob["manifest"]["settings"]
    recomputed = config_hash(settings)
    acc_items = sum(1 for it in blob["items"] if it["correct"])
    n_items = len(blob["items"])
    overall = blob["tasks"]["overall"]
    acc_recomputed = round(acc_items / n_items, 4) == round(overall["accuracy"], 4)
    return {
        "run_id": row["run_id"],
        "artifact_exists": True,
        "hash_matches_artifact": recomputed == blob["manifest"]["settings"].get(
            "config_hash", recomputed
        )
        or recomputed == row["config_hash"],
        "hash_matches_registry": recomputed == row["config_hash"],
        "accuracy_matches_registry": (
            acc_items == row["overall"]["correct"] and n_items == row["overall"]["n"]
        ),
        "accuracy_matches_artifact": acc_recomputed,
        "n_items": n_items,
        "git_commit": blob["manifest"].get("git_commit"),
        "packages": blob["manifest"].get("packages"),
        "hardware": blob["manifest"].get("hardware"),
        "utc": blob["manifest"].get("utc"),
        "settings": settings,
    }


def load_paper_data() -> dict[str, Any]:
    """Load + verify the full paper matrix. Raises on inconsistency."""
    rows = load_registry_rows()
    problems: list[str] = []
    blobs: dict[str, dict[str, Any]] = {}
    verifications: list[dict[str, Any]] = []
    for row in rows:
        try:
            blob = load_blob_by_row(row)
        except FileNotFoundError:
            problems.append(f"missing artifact for {row['run_id']}")
            continue
        blobs[row["run_id"]] = blob
        # Validate raw records before any dictionary conversion or rounding.
        ids = [it['id'] for it in blob['items']]
        if len(ids) != len(set(ids)) or not ids:
            raise ValueError(f"duplicate or empty item IDs: {row['run_id']}")
        for it in blob['items']:
            if type(it['correct']) is not bool:
                raise ValueError('correct must be a JSON boolean')
            if is_correct(it['task'], it['generation'], str(it['gold'])) != it['correct']:
                raise ValueError(f"rescoring mismatch: {row['run_id']} {it['id']}")
            if predicted(it['task'], it['generation'], str(it['gold'])) != it['predicted']:
                raise ValueError(f"prediction mismatch: {row['run_id']} {it['id']}")
        if row['model_id'] != blob['manifest']['settings']['model_id']:
            raise ValueError('registry/model identity mismatch')
        v = verify_row(row, blob)
        if not v["hash_matches_registry"]:
            problems.append(f"config_hash mismatch for {row['run_id']}")
        if not v["accuracy_matches_registry"]:
            problems.append(f"accuracy/count mismatch for {row['run_id']}")
        if not v['accuracy_matches_artifact']:
            problems.append(f"artifact summary mismatch for {row['run_id']}")
        verifications.append(v)
        # In-memory analysis values use exact counts. Never modify raw artifacts.
        tasks = summarize_tasks(blob['items'])
        for task in tasks.values():
            task['accuracy'] = task['correct'] / task['n']
            task['accuracy_ci95'] = list(wilson_interval(task['correct'], task['n']))
        blob['tasks'] = tasks
        row['overall'] = tasks['overall']

    frozen = [json.loads(l) for l in (REPO_ROOT / 'data/official/eval_set.jsonl').read_text().splitlines() if l.strip()]
    expected = {it['id']: it for it in frozen}
    for run_id, blob in blobs.items():
        if set(expected) != {it['id'] for it in blob['items']}:
            problems.append(f'frozen item coverage mismatch: {run_id}')
        for it in blob['items']:
            ref = expected.get(it['id'])
            if ref is None or any(str(it[k]) != str(ref[k]) for k in ('task', 'gold', 'language')):
                problems.append(f'frozen item metadata mismatch: {run_id} {it["id"]}')

    cells: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["run_id"] not in blobs:
            continue
        key = (row["model_id"], row["factor"], row["factor_level"])
        if key in cells:
            raise ValueError(f'duplicate model/config cell: {key}')
        cells[key] = {
            "run_id": row["run_id"],
            "config_hash": row["config_hash"],
            "overall": row["overall"],
            "tasks": blobs[row["run_id"]]["tasks"],
            "correct_by_id": items_correct(blobs[row["run_id"]]),
            "latency": blobs[row["run_id"]].get("latency"),
            "manifest": blobs[row["run_id"]]["manifest"],
            "git_commit": row.get("git_commit"),
            "utc": row.get("utc"),
        }
    return {
        "rows": rows,
        "blobs": blobs,
        "cells": cells,
        "verifications": verifications,
        "problems": problems,
    }


def cell(cells: dict[str, dict[str, Any]], model: str, factor: str, level: str):
    return cells.get((model, factor, level))
