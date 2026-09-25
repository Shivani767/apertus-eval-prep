"""Study compatibility helpers."""
from __future__ import annotations
from typing import Any, Mapping, Sequence
from apertus_eval_prep.core.errors import ArtifactError

STUDY_IDENTITY_FIELDS = (
    "study_id", "dataset_hash", "task_hash", "prompt_hash", "prompt_version",
    "metric_definition_version", "evidence_mode",
)


def identity(point: Mapping[str, Any]) -> dict[str, Any]:
    nested = point.get("identity") if isinstance(point.get("identity"), Mapping) else {}
    return {key: point.get(key, nested.get(key)) for key in STUDY_IDENTITY_FIELDS if key != "study_id"}


def validate_study_compatibility(
    points: Sequence[Mapping[str, Any]], *, expected_study_id: str | None = None,
    expected_evidence_mode: str | None = None,
) -> dict[str, Any]:
    conflicts = []
    study_ids = {
        str(point.get("study_id") or (point.get("identity") or {}).get("study_id"))
        for point in points
    }
    if expected_study_id is not None and study_ids != {expected_study_id}:
        conflicts.append({"field": "study_id", "expected": expected_study_id, "observed": sorted(study_ids)})
    observed_modes = {str(identity(point).get("evidence_mode") or "UNKNOWN") for point in points}
    if expected_evidence_mode is not None and observed_modes != {expected_evidence_mode}:
        conflicts.append({"field": "evidence_mode", "expected": expected_evidence_mode, "observed": sorted(observed_modes)})
    if points:
        reference = identity(points[0])
        for key in ("evidence_mode", "dataset_hash", "task_hash", "prompt_hash", "prompt_version", "metric_definition_version"):
            if reference.get(key) is None:
                conflicts.append({"run_index": 0, "field": key, "baseline": None, "candidate": None})
        for index, point in enumerate(points[1:], start=1):
            current = identity(point)
            for field in STUDY_IDENTITY_FIELDS:
                if reference.get(field) != current.get(field):
                    conflicts.append({"run_index": index, "field": field, "baseline": reference.get(field), "candidate": current.get(field)})
    if conflicts:
        raise ArtifactError("study run artifacts are incompatible", conflicts=conflicts, required_matching_fields=list(STUDY_IDENTITY_FIELDS))
    return {"compatible": True, "conflicts": [], "required_matching_fields": list(STUDY_IDENTITY_FIELDS)}


__all__ = ["STUDY_IDENTITY_FIELDS", "identity", "validate_study_compatibility"]
