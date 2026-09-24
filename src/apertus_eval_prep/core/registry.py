"""Run index for ``runs/index.jsonl``.

The source of truth is always the per-run ``manifest.json``; the index is an
append-only convenience log for humans and CI (who ran what, when, with which
gate status). ``find_runs`` therefore scans manifests rather than trusting the
index, so a deleted or moved run can never be reported as present.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from apertus_eval_prep.core.artifacts import INDEX, RunSummary, iter_runs
from apertus_eval_prep.utils.serialization import append_jsonl, read_jsonl
from apertus_eval_prep.utils.pii import redact_for_artifact


def append_index(root: str | Path, summary: RunSummary) -> Path:
    """Append one run summary to ``<root>/index.jsonl``."""
    return append_jsonl(Path(root) / INDEX, [redact_for_artifact(summary.to_dict())])


def load_index(root: str | Path) -> list[dict[str, Any]]:
    """Read the convenience index (empty when it does not exist yet)."""
    return list(read_jsonl(Path(root) / INDEX))


def find_runs(
    root: str | Path,
    *,
    run_id: str | None = None,
    experiment_id: str | None = None,
    model_id: str | None = None,
    config_hash: str | None = None,
    evidence_class: str | None = None,
    tag: str | None = None,
    latest: bool = False,
) -> list[RunSummary]:
    """Filter runs by manifest fields; ``latest=True`` returns only the newest match."""
    matches: list[RunSummary] = []
    for summary in iter_runs(root):
        if run_id is not None and summary.run_id != run_id:
            continue
        if experiment_id is not None and summary.experiment_id != experiment_id:
            continue
        if model_id is not None and summary.model_id != model_id:
            continue
        if config_hash is not None and summary.config_hash != config_hash:
            continue
        if evidence_class is not None and summary.evidence_class != evidence_class:
            continue
        if tag is not None and tag not in _manifest_tags(summary.directory):
            continue
        matches.append(summary)
    matches.sort(key=lambda s: (s.utc or "", s.run_id))
    if latest and matches:
        return [matches[-1]]
    return matches


def _manifest_tags(run_dir: Path) -> list[str]:
    from apertus_eval_prep.core.artifacts import load_run_manifest

    try:
        manifest = load_run_manifest(run_dir)
    except Exception:  # a broken manifest must not crash a listing
        return []
    tags = manifest.get("tags")
    if isinstance(tags, list):
        return [str(t) for t in tags]
    return []


def experiment_runs(root: str | Path, experiment_id: str) -> list[RunSummary]:
    """All runs belonging to one experiment, oldest first."""
    return find_runs(root, experiment_id=experiment_id)
