"""Create a sanitized, dimension-scoped review package from a run."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apertus_eval_prep.review.sampling import sample_review_candidates
from apertus_eval_prep.review.schema import REVIEW_DIMENSIONS, validate_annotation
from apertus_eval_prep.utils.hashing import stable_hash
from apertus_eval_prep.utils.serialization import write_jsonl


def export_review_package(
    run_dir: str | Path, out: str | Path, *, dimensions: list[str] | None = None,
    sample_size: int = 50, strategy: str = "stratified", seed: int = 0,
    baseline_run: str | Path | None = None, study_id: str = "REPLACE_WITH_STUDY_ID",
    rubric_version: str = "phase8-v1",
) -> dict[str, Any]:
    """Write template annotations; templates never claim completed human review."""
    selected = sample_review_candidates(
        run_dir, sample_size=sample_size, strategy=strategy, seed=seed, baseline_run=baseline_run
    )
    dims = [str(x) for x in (dimensions or REVIEW_DIMENSIONS)]
    timestamp = datetime.now(timezone.utc).isoformat()
    records: list[dict[str, Any]] = []
    for item in selected:
        for dimension in dims:
            identity = f"{item['item_id']}:{dimension}"
            records.append(validate_annotation({
                "annotation_id": f"review:{stable_hash(identity)}", "study_id": study_id,
                "run_id": item.get("run_id", ""), "example_id": item.get("example_id"),
                "episode_id": item.get("episode_id"), "task": item.get("task"), "domain": item.get("domain"),
                "language": item.get("language"), "dimension": dimension, "rubric_version": rubric_version,
                "label": None, "score": None, "confidence": None, "annotator_id_hash": None,
                "review_timestamp": None,
                "sanitized_prompt": item.get("sanitized_prompt"),
                "sanitized_context": item.get("sanitized_context"),
                "sanitized_output": item.get("sanitized_output"),
                "notes": "", "adjudication_status": "pending",
                "evidence_references": {
                    "run_directory": str(run_dir), "raw_output": "raw_outputs.jsonl",
                    "scored_example": "scored_examples.jsonl", "item_id": item["item_id"],
                    "evidence_mode": item.get("evidence_mode"),
                    "sanitized_prompt": item.get("sanitized_prompt"),
                    "sanitized_context": item.get("sanitized_context"),
                    "sanitized_output": item.get("sanitized_output"),
                },
                "status": "template", "exported_at": timestamp,
            }, require_completed=False))
    path = write_jsonl(out, records)
    return {"path": str(path), "n_records": len(records), "n_items": len(selected),
            "dimensions": dims, "status": "TEMPLATE_ONLY", "human_reviewed": False}


__all__ = ["export_review_package"]
