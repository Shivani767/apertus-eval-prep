"""Import completed, privacy-safe annotations and produce agreement evidence."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from apertus_eval_prep.core.evidence import REAL_EVIDENCE_MODES
from apertus_eval_prep.review.agreement import agreement_summary
from apertus_eval_prep.review.schema import ReviewValidationError, validate_annotation
from apertus_eval_prep.utils.serialization import read_json, read_jsonl, write_json


def _linked_real_annotation(row: Mapping[str, Any]) -> bool:
    """Require a readable, matching run manifest before claiming review evidence."""
    refs = row.get("evidence_references") or {}
    if str(refs.get("evidence_mode", "")).upper() not in REAL_EVIDENCE_MODES:
        return False
    raw_directory = refs.get("run_directory") or refs.get("run_dir")
    if not raw_directory:
        return False
    directory = Path(str(raw_directory)).expanduser()
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        return False
    try:
        manifest = read_json(manifest_path)
    except (OSError, TypeError, ValueError):
        return False
    return isinstance(manifest, Mapping) and str(manifest.get("run_id") or "") == str(row.get("run_id") or "")


def ingest_annotations(
    input_path: str | Path, out: str | Path, *, study_id: str | None = None,
) -> dict[str, Any]:
    """Validate completed annotations, reject duplicates, and write a summary."""
    records = read_jsonl(input_path)
    if not records:
        raise ReviewValidationError("annotation input is empty; templates do not establish human review")
    validated: list[dict[str, Any]] = []
    seen: set[str] = set()
    reviewer_items: set[tuple[str, str, str, str]] = set()
    rubric_versions: set[str] = set()
    linked_runs: set[str] = set()
    for index, record in enumerate(records, start=1):
        if not isinstance(record, Mapping):
            raise ReviewValidationError(f"annotation line {index} must be an object")
        row = validate_annotation(record, require_completed=True)
        if study_id and row["study_id"] != study_id:
            raise ReviewValidationError(f"annotation {row['annotation_id']} does not belong to study {study_id}")
        if row["annotation_id"] in seen:
            raise ReviewValidationError(f"duplicate annotation_id: {row['annotation_id']}")
        seen.add(row["annotation_id"])
        reviewer_item = (
            str(row["run_id"]), str(row.get("example_id") or row.get("episode_id")),
            str(row["dimension"]), str(row["annotator_id_hash"]),
        )
        if reviewer_item in reviewer_items:
            raise ReviewValidationError(
                f"duplicate annotation for reviewer/item/dimension: {reviewer_item}"
            )
        reviewer_items.add(reviewer_item)
        rubric_versions.add(str(row["rubric_version"]))
        linked_runs.add(str(row["run_id"]))
        validated.append(row)
    if len(rubric_versions) > 1:
        raise ReviewValidationError("all completed annotations in one import must use one rubric_version")
    real_annotations = [row for row in validated if _linked_real_annotation(row)]
    human_reviewed = bool(real_annotations)
    agreement = agreement_summary(validated)
    dimensions = Counter(str(row["dimension"]) for row in validated)
    payload = {
        "schema_version": "1.0",
        "study_id": study_id or validated[0]["study_id"],
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "n_annotations": len(validated),
        "n_completed": len(validated),
        "n_linked_runs": len(linked_runs),
        "rubric_version": next(iter(rubric_versions)),
        "dimensions": dict(sorted(dimensions.items())),
        "human_reviewed": human_reviewed,
        "human_review_status": "COMPLETED_NON_SYNTHETIC_ANNOTATIONS" if human_reviewed else "ANNOTATIONS_ONLY_FOR_SYNTHETIC_EVIDENCE",
        "agreement": agreement,
        "annotations": validated,
        "limitations": [
            "Human review is limited to the linked runs, dimensions, rubric version, and completed records.",
            "Agreement measures reviewer consistency, not correctness, validity, safety, or production readiness.",
        ],
    }
    write_json(out, payload)
    return payload


def review_evidence_for_runs(payload: Mapping[str, Any]) -> dict[str, bool]:
    """Return conservative per-run human-review flags."""
    linked = {
        str(row.get("run_id")): (
            bool(payload.get("human_reviewed")) and _linked_real_annotation(row)
        )
        for row in payload.get("annotations") or [] if isinstance(row, Mapping)
    }
    return linked


__all__ = ["ingest_annotations", "review_evidence_for_runs"]
