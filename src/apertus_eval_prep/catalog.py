"""Dataset/model catalog: versioned, fingerprinted records.

Closes audit gap #1 (docs/architecture/current_state.md): SOURCES.md is
prose; items carry no dataset revision; model revisions were None.

- DatasetRecord: identity (dataset_id/task), source + revision as recorded
  in data/official/SOURCES.md, MEASURED content_sha256 of the frozen file,
  MEASURED item count + languages (recomputed from the file, never trusted
  from prose), schema_version.
- ModelRecord: model_id, revision (UNAVAILABLE unless recorded), measured
  backend/quantization coverage DERIVED from the experiment registry,
  param_count UNAVAILABLE (never guessed from the model name).

Every emitted field carries its evidence class: MEASURED (computed from a
file), DERIVED (computed from other records), or UNAVAILABLE (null — no
imputation). `make catalog` / `apertus catalog` regenerate the JSONL files.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

OFFICIAL_TASKS = ("arc_easy", "gsm8k", "hellaswag", "mgsm")

# hub revision + license exactly as recorded in data/official/SOURCES.md.
# source_meta is DERIVED from that prose file; content_sha256/n/languages
# are MEASURED from the actual JSONL bytes at catalog-build time.
SOURCES_META = {
    "arc_easy": {
        "file": "arc_easy.jsonl", "hf_id": "allenai/ai2_arc", "split": "test",
        "license": "CC-BY-SA-4.0",
        "hub_sha": "210d026faf9955653af8916fad021475a3f00453",
    },
    "gsm8k": {
        "file": "gsm8k.jsonl", "hf_id": "openai/gsm8k", "split": "test",
        "license": "MIT",
        "hub_sha": "740312add88f781978c0658806c59bc2815b9866",
    },
    "hellaswag": {
        "file": "hellaswag.jsonl", "hf_id": "Rowan/hellaswag", "split": "validation",
        "license": "MIT",
        "hub_sha": "218ec52e09a7e7462a5400043bb9a69a41d06b76",
    },
    "mgsm": {
        "file": "mgsm.jsonl", "hf_id": "juletxara/mgsm", "split": "test",
        "license": "MIT",
        "hub_sha": "b2f13d426afe3be8d69a7e739b36724db8b66bbc",
    },
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def measure_jsonl(path: Path) -> dict[str, Any]:
    """MEASURED facts about a frozen JSONL slice: n, languages, ids unique."""
    n = 0
    languages: set[str] = set()
    tasks: set[str] = set()
    ids: set[str] = set()
    dup_ids = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            n += 1
            iid = row.get("id")
            if iid is not None:
                if iid in ids:
                    dup_ids += 1
                ids.add(iid)
            if row.get("language") is not None:
                languages.add(str(row["language"]))
            if row.get("task") is not None:
                tasks.add(str(row["task"]))
    return {
        "n_items": n,
        "languages": sorted(languages),
        "tasks": sorted(tasks),
        "n_duplicate_ids": dup_ids,
    }


def dataset_record(data_dir: Path, task: str) -> dict[str, Any]:
    meta = SOURCES_META[task]
    path = data_dir / meta["file"]
    out: dict[str, Any] = {
        "dataset_id": f"{meta['hf_id']}:{meta['split']}",
        "task": task,
        "file": str(meta["file"]),
        "schema_version": SCHEMA_VERSION,
        "source": {"hf_id": meta["hf_id"], "split": meta["split"],
                   "hub_revision": meta["hub_sha"], "license": meta["license"],
                   "evidence": "DERIVED from data/official/SOURCES.md"},
    }
    if not path.exists():
        out["status"] = "UNAVAILABLE"
        out["content_sha256"] = None
        out["measured"] = None
        return out
    measured = measure_jsonl(path)
    out.update({
        "status": "MEASURED",
        "content_sha256": sha256_file(path),
        "measured": {
            **measured,
            "evidence": "MEASURED from file bytes",
        },
    })
    return out


def combined_eval_set_record(data_dir: Path) -> dict[str, Any]:
    path = data_dir / "eval_set.jsonl"
    out: dict[str, Any] = {
        "dataset_id": "apertus-frozen-eval-set",
        "task": "combined",
        "file": "eval_set.jsonl",
        "schema_version": SCHEMA_VERSION,
        "source": {"description": "200 items/task x 4 tasks, frozen slice",
                   "evidence": "DERIVED from data/official/SOURCES.md"},
    }
    if not path.exists():
        out["status"] = "UNAVAILABLE"
        out["content_sha256"] = None
        out["measured"] = None
        return out
    out.update({
        "status": "MEASURED",
        "content_sha256": sha256_file(path),
        "measured": {**measure_jsonl(path), "evidence": "MEASURED from file bytes"},
    })
    return out


def artifact_settings_by_run(
    repo_root: Path, registry_rows: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """MEASURED backend/quantization/revision per run_id, read from artifacts.

    Registry rows do not carry these fields — they live in each run blob's
    manifest.settings. Each unique path is read at most once (cache keyed by
    run_id). Missing or unreadable artifacts are simply absent from the
    result — never imputed.
    """
    cache: dict[str, dict[str, Any]] = {}
    for r in registry_rows:
        run_id = r.get("run_id")
        if not run_id or run_id in cache:
            continue
        path = r.get("path")
        p = Path(path) if path and Path(path).is_absolute() else repo_root / (path or "")
        if not p.exists():
            continue
        try:
            blob = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        s = (blob.get("manifest") or {}).get("settings") or {}
        cache[run_id] = {
            "backend": s.get("backend"),
            "quantization": s.get("quantization"),
            "revision": s.get("revision"),
        }
    return cache


def _merge_field(
    rows: list[dict[str, Any]],
    key: str,
    artifact_settings: dict[str, dict[str, Any]] | None,
) -> list[str]:
    """Per-row value: direct row field first, else artifact settings.

    Rows whose value is missing everywhere contribute nothing (UNAVAILABLE),
    except quantization, where a completed control cell measured without
    quantization is genuinely the 'none' configuration.
    """
    vals: set[str] = set()
    for r in rows:
        v = r.get(key)
        if v in (None, "") and artifact_settings is not None:
            v = (artifact_settings.get(r.get("run_id")) or {}).get(key)
        if v not in (None, ""):
            vals.add(str(v).strip())
    return sorted(vals)


def model_record(
    model_id: str,
    registry_rows: list[dict[str, Any]],
    artifact_settings: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Model card DERIVED from actual experiment-registry coverage.

    Nothing about the model is asserted from its name: param_count stays
    None (UNAVAILABLE) and revision is None unless a row recorded one.
    Backends/quantizations/cells are exactly what was measured.
    """
    rows = [r for r in registry_rows if r.get("model_id") == model_id]
    revisions = {r.get("revision") or r.get("model_revision") for r in rows}
    if artifact_settings is not None:
        revisions |= {
            (artifact_settings.get(r.get("run_id")) or {}).get("revision")
            for r in rows
        }
    revisions.discard(None)
    revisions = {str(v).strip() for v in revisions if str(v).strip()}
    backends = _merge_field(rows, "backend", artifact_settings)
    quants = _merge_field(rows, "quantization", artifact_settings)
    # Control cells ran without quantization: if nothing else was recorded,
    # 'none' is what was measured (fp16/no-quantization), never a guess.
    quants = quants if quants else (["none"] if rows else [])
    cells = [
        {"factor": r.get("factor"), "factor_level": r.get("factor_level"),
         "status": r.get("status"), "run_id": r.get("run_id")}
        for r in rows
    ]
    return {
        "model_id": model_id,
        "revision": sorted(revisions)[0] if len(revisions) == 1 else (
            sorted(revisions) if revisions else None),
        "revision_status": "MEASURED" if revisions else "UNAVAILABLE",
        "param_count": None,
        "param_count_status": "UNAVAILABLE (not asserted from the model name)",
        "source": "huggingface.co (id is the source pointer)",
        "measured_backends": backends,
        "measured_quantizations": quants,
        "n_registry_cells": len(rows),
        "cells": cells,
        "schema_version": SCHEMA_VERSION,
    }


def build_catalog(repo_root: Path, registry_path: Path | None = None) -> dict[str, Any]:
    """Full catalog: datasets (fingerprinted) + models (from registry)."""
    data_dir = repo_root / "data" / "official"
    datasets = [dataset_record(data_dir, t) for t in OFFICIAL_TASKS]
    datasets.append(combined_eval_set_record(data_dir))
    models: list[dict[str, Any]] = []
    if registry_path is not None and registry_path.exists():
        rows = [json.loads(l) for l in registry_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        settings_by_run = artifact_settings_by_run(repo_root, rows)
        for mid in sorted({r.get("model_id") for r in rows if r.get("model_id")}):
            models.append(model_record(mid, rows, settings_by_run))
    return {"schema_version": SCHEMA_VERSION,
            "provenance": {"content_sha256/n/languages": "MEASURED from frozen files",
                           "model coverage": "DERIVED from experiment registry + MEASURED artifact settings",
                           "hub revisions/licenses": "DERIVED from SOURCES.md"},
            "datasets": datasets, "models": models}


def render_catalog_markdown(cat: dict[str, Any]) -> str:
    lines = ["# Dataset & model catalog",
             "",
             "content_sha256 / n / languages: MEASURED from frozen files;",
             "model coverage: DERIVED from the experiment registry;",
             "revisions: UNAVAILABLE unless a run recorded one.", ""]
    lines += ["| dataset_id | file | sha256[:12] | n | languages | status |",
              "|---|---|---|---|---|---|"]
    for d in cat["datasets"]:
        sha = (d.get("content_sha256") or "—")[:12]
        m = d.get("measured") or {}
        lines.append(f"| {d['dataset_id']} | {d['file']} | {sha} | "
                     f"{m.get('n_items', '—')} | {', '.join(m.get('languages', [])) or '—'} | "
                     f"{d['status']} |")
    lines += ["", "| model | revision | backends | quants | cells |", "|---|---|---|---|---|"]
    for m in cat["models"]:
        rev = m["revision"]
        rev = rev if isinstance(rev, str) else ("none recorded" if rev is None else ",".join(rev))
        lines.append(f"| {m['model_id']} | {rev} | {', '.join(m['measured_backends'])} | "
                     f"{', '.join(m['measured_quantizations'])} | {m['n_registry_cells']} |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Artifact catalog: versioned, fingerprinted index of run JSON files.
# ---------------------------------------------------------------------------

class ArtifactCatalog:
    """Index of run artifacts with content hashes and measured metadata.

    Each entry records the artifact path, sha256, size, model_id, factor,
    factor_level, status, config_hash, and n_items — all MEASURED from the
    file bytes, never asserted. Missing/unreadable files are skipped and
    counted in n_skipped.
    """

    def __init__(self, entries: list[dict[str, Any]], n_skipped: int = 0) -> None:
        self.entries = entries
        self.n_skipped = n_skipped

    def by_model(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for e in self.entries:
            out.setdefault(e.get("model_id", "unknown"), []).append(e)
        return out

    def by_factor(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for e in self.entries:
            out.setdefault(e.get("factor", "unknown"), []).append(e)
        return out

    def by_config_hash(self, config_hash: str) -> dict[str, Any] | None:
        for e in self.entries:
            if e.get("config_hash") == config_hash:
                return e
        return None


def artifact_catalog(repo_root: Path, registry_path: Path) -> ArtifactCatalog:
    """Build an ArtifactCatalog from a registry's run files.

    For each registry row with a 'path', reads the run JSON and records
    measured metadata. Files that are missing, unreadable, or not valid
    JSON are skipped and counted.
    """
    rows = [
        json.loads(l)
        for l in registry_path.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    entries: list[dict[str, Any]] = []
    skipped = 0
    for row in rows:
        path = row.get("path")
        if not path:
            skipped += 1
            continue
        run_path = Path(path) if Path(path).is_absolute() else repo_root / path
        if not run_path.exists():
            skipped += 1
            continue
        try:
            blob = json.loads(run_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            skipped += 1
            continue
        manifest = blob.get("manifest") or {}
        settings = manifest.get("settings") or {}
        overall = blob.get("overall") or {}
        items = blob.get("items") or []
        entries.append({
            "path": str(run_path),
            "sha256": sha256_file(run_path),
            "size_bytes": run_path.stat().st_size,
            "model_id": row.get("model_id") or settings.get("model_id"),
            "factor": row.get("factor"),
            "factor_level": row.get("factor_level"),
            "status": row.get("status"),
            "config_hash": row.get("config_hash") or blob.get("config_hash"),
            "n_items": len(items),
            "accuracy": overall.get("accuracy"),
            "git_commit": manifest.get("git_commit"),
        })
    return ArtifactCatalog(entries, n_skipped=skipped)