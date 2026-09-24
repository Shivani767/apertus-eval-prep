"""Ingest completed run artifacts into Phase 5 deployment comparison points."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from apertus_eval_prep.core.artifacts import (
    CONFIDENCE_INTERVALS, FAILURE_FINGERPRINT, GATE_REPORT, MANIFEST, METRICS,
    load_run_manifest,
)
from apertus_eval_prep.core.errors import ArtifactError
from apertus_eval_prep.core.evidence import evidence_from_manifest
from apertus_eval_prep.release.deployment import CostModel, summarize_deployment
from apertus_eval_prep.utils.serialization import read_json

_IDENTITY_FIELDS = (
    "dataset_hash", "task_hash", "prompt_hash", "prompt_version",
    "metric_definition_version", "evidence_mode",
)


def _read_required(directory: Path, name: str) -> dict[str, Any]:
    path = directory / name
    if not path.exists():
        raise ArtifactError(f"run artifact is missing: {path}", run_dir=str(directory))
    try:
        payload = read_json(path)
    except Exception as exc:
        raise ArtifactError(f"invalid run artifact {path}: {exc}", run_dir=str(directory)) from exc
    if not isinstance(payload, Mapping):
        raise ArtifactError(f"run artifact must be a JSON object: {path}", run_dir=str(directory))
    return dict(payload)


def _optional(directory: Path, name: str) -> dict[str, Any]:
    path = directory / name
    if not path.exists():
        return {}
    try:
        payload = read_json(path)
    except Exception as exc:
        raise ArtifactError(f"invalid run artifact {path}: {exc}", run_dir=str(directory)) from exc
    return dict(payload) if isinstance(payload, Mapping) else {}


def _identity(manifest: Mapping[str, Any], metrics: Mapping[str, Any]) -> dict[str, Any]:
    dataset = manifest.get("dataset") if isinstance(manifest.get("dataset"), Mapping) else {}
    task = manifest.get("task") if isinstance(manifest.get("task"), Mapping) else {}
    prompt = manifest.get("prompt") if isinstance(manifest.get("prompt"), Mapping) else {}
    evidence = evidence_from_manifest(manifest)
    return {
        "dataset_hash": manifest.get("dataset_hash") or dataset.get("hash"),
        "task_hash": manifest.get("task_hash") or task.get("hash"),
        "prompt_hash": manifest.get("prompt_hash") or prompt.get("prompt_hash") or prompt.get("template_hash"),
        "prompt_version": prompt.get("version") or prompt.get("prompt_id"),
        "metric_definition_version": manifest.get("metric_definition_version") or metrics.get("schema_version"),
        "evidence_mode": evidence.get("mode"),
    }



def ingest_run_directory(run_dir: str | Path) -> dict[str, Any]:
    """Build one Phase 5-compatible point without rerunning the model."""
    directory = Path(run_dir)
    manifest = load_run_manifest(directory)
    metrics = _read_required(directory, METRICS)
    confidence = _optional(directory, CONFIDENCE_INTERVALS)
    gate = _optional(directory, GATE_REPORT)
    fingerprint = _optional(directory, FAILURE_FINGERPRINT)
    try:
        evidence = evidence_from_manifest(manifest)
    except ValueError as exc:
        raise ArtifactError(f"invalid evidence metadata in {directory}: {exc}", run_dir=str(directory)) from exc
    model = manifest.get("model") if isinstance(manifest.get("model"), Mapping) else {}
    backend = manifest.get("backend") if isinstance(manifest.get("backend"), Mapping) else {}
    identity = _identity(manifest, metrics)
    cost = CostModel.from_mapping(manifest.get("cost") or metrics.get("cost_config"))
    point = summarize_deployment(metrics, cost_model=cost)
    point.update({
        "evidence": evidence,
        "evidence_mode": evidence.get("mode"),
        "runtime_profile": manifest.get("runtime_profile"),
        "hardware_profile": manifest.get("runtime_profile"),
        "run_id": manifest.get("run_id") or directory.name,
        "run_directory": str(directory),
        "label": f"{model.get('model_id') or manifest.get('model_id') or 'model'}@"
                 f"{model.get('model_revision') or manifest.get('model_revision') or 'unpinned'}",
        "configuration_id": manifest.get("config_hash"),
        "config_hash": manifest.get("config_hash"),
        "metric_definition_version": identity["metric_definition_version"],
        "dataset_hash": identity["dataset_hash"],
        "task_hash": identity["task_hash"],
        "prompt_hash": identity["prompt_hash"],
        "prompt_version": identity["prompt_version"],
        "model_id": point.get("model_id") or model.get("model_id") or manifest.get("model_id"),
        "model_revision": point.get("model_revision") or model.get("model_revision") or manifest.get("model_revision"),
        "tokenizer_id": point.get("tokenizer_id") or model.get("tokenizer_id"),
        "tokenizer_revision": point.get("tokenizer_revision") or model.get("tokenizer_revision"),
        "backend": point.get("backend") or model.get("adapter_kind"),
        "device": point.get("device") or backend.get("device"),
        "precision": point.get("precision") or backend.get("precision"),
        "quantization": point.get("quantization") or backend.get("quantization"),
        "known_limitations": list(evidence.get("known_limitations") or []),
        "confidence_intervals": confidence or metrics.get("confidence_intervals"),
        "gate_status": gate.get("status") or (metrics.get("release_gate") or {}).get("status"),
        "failure_fingerprint": {
            "n_failures": fingerprint.get("n_failures"),
            "failure_rate": fingerprint.get("failure_rate"),
            "top_investigation_priority": fingerprint.get("top_investigation_priority"),
        },
        "identity": identity,
        "source_artifacts": {
            MANIFEST: True, METRICS: True, CONFIDENCE_INTERVALS: bool(confidence),
            GATE_REPORT: bool(gate), FAILURE_FINGERPRINT: bool(fingerprint),
        },
    })
    return point



def ingest_run_directories(
    run_dirs: Sequence[str | Path], *, allow_incompatible: bool = False
) -> dict[str, Any]:
    """Ingest runs and reject comparisons with incompatible evaluation identities."""
    if not run_dirs:
        raise ArtifactError("at least one run directory is required")
    points = [ingest_run_directory(path) for path in run_dirs]
    identities = [point["identity"] for point in points]
    reference = identities[0]
    conflicts: list[dict[str, Any]] = []
    for index, identity in enumerate(identities[1:], start=1):
        for field in _IDENTITY_FIELDS:
            left, right = reference.get(field), identity.get(field)
            if left != right:
                conflicts.append({"run_index": index, "field": field, "baseline": left, "candidate": right})
    if conflicts and not allow_incompatible:
        raise ArtifactError(
            "run artifacts are incompatible for deployment comparison",
            conflicts=conflicts,
            required_matching_fields=list(_IDENTITY_FIELDS),
        )
    return {
        "schema_version": "1.0",
        "points": points,
        "compatibility": {
            "compatible": not conflicts,
            "conflicts": conflicts,
            "required_matching_fields": list(_IDENTITY_FIELDS),
            "allow_incompatible": allow_incompatible,
        },
    }


__all__ = ["ingest_run_directory", "ingest_run_directories"]
