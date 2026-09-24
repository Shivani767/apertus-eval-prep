"""Immutable run artifact directories.

Layout produced for every run::

    runs/<run_id>/
        manifest.json          provenance (git, env, hashes, backend)
        config.resolved.yaml   fully resolved configuration actually used
        dataset.lock.json      dataset path + hash + example count
        prompts/               prompt protocol + rendered prompt samples
        raw_outputs.jsonl      raw model/system outputs (append-only)
        scored_examples.jsonl  derived per-example scores
        tool_traces.jsonl      per-step tool traces (episodes only)
        metrics.json           aggregates + uncertainty + gate decision
        confidence_intervals.json
        failures.jsonl         failure records (fingerprint input)
        gate_report.json       release-gate decision for CI consumers
        report.md / report.html

Guarantees: a run directory is created once and never overwritten silently
(colliding ids raise), raw observations are kept separate from derived scores,
and raw retention is governed by an explicit policy.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from apertus_eval_prep.core.errors import ArtifactError, ArtifactExistsError
from apertus_eval_prep.utils.hashing import short_id
from apertus_eval_prep.utils.pii import (
    RedactionPolicy,
    redact_for_artifact,
    redact_structure,
    redact_text_for_artifact,
    redact_text_for_report,
    sanitize_for_report,
)
from apertus_eval_prep.utils.serialization import (
    append_jsonl,
    read_json,
    read_yaml,
    write_json,
    write_text,
    write_yaml,
)

MANIFEST = "manifest.json"
RESOLVED_CONFIG = "config.resolved.yaml"
DATASET_LOCK = "dataset.lock.json"
PROMPTS_DIR = "prompts"
PROMPT_PROTOCOL = "prompts/prompt_protocol.json"
RAW_OUTPUTS = "raw_outputs.jsonl"
SCORED_EXAMPLES = "scored_examples.jsonl"
TOOL_TRACES = "tool_traces.jsonl"
SAFETY_REPORT_MD = "safety_report.md"
SAFETY_REPORT_HTML = "safety_report.html"
FAILURE_FINGERPRINT = "failure_fingerprint.json"
METRICS = "metrics.json"
CONFIDENCE_INTERVALS = "confidence_intervals.json"
FAILURES = "failures.jsonl"
GATE_REPORT = "gate_report.json"
REPORT_MD = "report.md"
REPORT_HTML = "report.html"
INDEX = "index.jsonl"

ALL_ARTIFACTS: tuple[str, ...] = (
    MANIFEST,
    RESOLVED_CONFIG,
    DATASET_LOCK,
    PROMPT_PROTOCOL,
    RAW_OUTPUTS,
    SCORED_EXAMPLES,
    TOOL_TRACES,
    SAFETY_REPORT_MD,
    SAFETY_REPORT_HTML,
    FAILURE_FINGERPRINT,
    METRICS,
    CONFIDENCE_INTERVALS,
    FAILURES,
    GATE_REPORT,
    REPORT_MD,
    REPORT_HTML,
)

_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,120}$")


@dataclass(frozen=True)
class RetentionPolicy:
    """How much raw content is allowed into the artifact directory."""

    include_raw_outputs: bool = True
    max_chars: int = 4000
    pii_redaction: bool = True

    def __post_init__(self) -> None:
        if self.max_chars < 0:
            raise ValueError("max_chars must be >= 0")


def retained_text_payload(
    text: str | None, retention: RetentionPolicy, *, field: str = "text"
) -> dict[str, Any]:
    """Return a raw-observation text field without bypassing retention policy."""
    original = "" if text is None else str(text)
    policy = RedactionPolicy(enabled=retention.pii_redaction)
    if not retention.include_raw_outputs:
        safe_for_hash = redact_for_artifact(original)
        return {
            field: "[RAW_RETENTION_DISABLED]",
            f"{field}_sha256": hashlib.sha256(str(safe_for_hash).encode("utf-8")).hexdigest()[:16],
            f"{field}_length": len(original),
        }
    return {field: sanitize_for_report(original, policy, max_chars=retention.max_chars)}


def sanitize_response_payload(
    response: Any, retention: RetentionPolicy
) -> dict[str, Any]:
    """Convert an adapter response into a safe, auditable observation payload."""
    payload = response.to_dict() if hasattr(response, "to_dict") else dict(response)
    policy = RedactionPolicy(enabled=retention.pii_redaction)
    payload = redact_structure(payload, policy)
    text_payload = retained_text_payload(str(payload.get("text") or ""), retention)
    payload.update(text_payload)
    # PII can be disabled for a local review artifact, but credentials are
    # never allowed to cross the persistence boundary.
    return redact_for_artifact(payload)


def sanitize_run_id(run_id: str) -> str:
    """Validate an explicit run id; runner ids are filesystem-safe by construction."""
    if not _SAFE_RUN_ID.match(run_id):
        raise ArtifactError(
            "run_id must match [A-Za-z0-9][A-Za-z0-9._-]{2,120}",
            run_id=run_id,
        )
    return run_id


def slugify(text: str, *, max_len: int = 40) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text.strip().lower()).strip("-")
    return (slug or "run")[:max_len]


def generate_run_id(run_name: str, config_hash: str, *, explicit: str | None = None) -> str:
    """Collision-resistant id: UTC stamp + name slug + config/fingerprint hash."""
    if explicit:
        return sanitize_run_id(explicit)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    fingerprint = short_id(config_hash, stamp, slugify(run_name), length=8)
    return sanitize_run_id(f"{stamp}-{slugify(run_name)}-{fingerprint}")


class RunStore:
    """Writer/reader for a single run directory."""

    def __init__(self, directory: str | Path, *, run_id: str, retention: RetentionPolicy) -> None:
        self.directory = Path(directory)
        self.run_id = run_id
        self.retention = retention

    @classmethod
    def create(
        cls,
        root: str | Path,
        *,
        run_name: str,
        config_hash: str,
        retention: RetentionPolicy | None = None,
        run_id: str | None = None,
    ) -> RunStore:
        """Create a new run directory; raise if the id already exists."""
        policy = retention or RetentionPolicy()
        resolved_id = generate_run_id(run_name, config_hash, explicit=run_id)
        directory = Path(root) / resolved_id
        if directory.exists():
            raise ArtifactExistsError(
                f"run directory already exists (runs are never overwritten): {directory}",
                run_id=resolved_id,
            )
        try:
            (directory / PROMPTS_DIR).mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:  # pragma: no cover - race guard
            raise ArtifactExistsError(f"run directory already exists: {directory}") from exc
        return cls(directory, run_id=resolved_id, retention=policy)

    # -- writing ---------------------------------------------------------
    def artifact_path(self, name: str) -> Path:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ArtifactError(f"artifact name must stay inside the run directory: {name!r}")
        root = self.directory.resolve()
        target = (self.directory / relative).resolve()
        if target != root and root not in target.parents:
            raise ArtifactError(f"artifact name must stay inside the run directory: {name!r}")
        return target

    def write_json(self, name: str, payload: Any) -> Path:
        return write_json(self.artifact_path(name), redact_for_artifact(payload))

    def write_yaml(self, name: str, payload: Any) -> Path:
        return write_yaml(self.artifact_path(name), redact_for_artifact(payload))

    def write_text(self, name: str, text: str) -> Path:
        return write_text(self.artifact_path(name), redact_text_for_report(text))

    def append_jsonl(self, name: str, records: Iterable[Any]) -> Path:
        safe_records = (redact_for_artifact(record) for record in records)
        return append_jsonl(self.artifact_path(name), safe_records)

    # -- reading ---------------------------------------------------------
    def read_json(self, name: str) -> Any:
        return read_json(self.artifact_path(name))

    def has(self, name: str) -> bool:
        return self.artifact_path(name).exists()


@dataclass
class RunSummary:
    """Cheap description of a run directory (from manifest + metrics only)."""

    run_id: str
    directory: Path
    run_name: str | None = None
    experiment_id: str | None = None
    parent_experiment_id: str | None = None
    model_id: str | None = None
    config_hash: str | None = None
    evidence_class: str | None = None
    conditions: dict[str, Any] | None = None
    utc: str | None = None
    accuracy: float | None = None
    n_scored: int | None = None
    gate_status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "directory": str(self.directory),
            "run_name": self.run_name,
            "experiment_id": self.experiment_id,
            "parent_experiment_id": self.parent_experiment_id,
            "model_id": self.model_id,
            "config_hash": self.config_hash,
            "evidence_class": self.evidence_class,
            "conditions": dict(self.conditions or {}),
            "utc": self.utc,
            "accuracy": self.accuracy,
            "n_scored": self.n_scored,
            "gate_status": self.gate_status,
        }


def load_run_manifest(run_dir: str | Path) -> dict[str, Any]:
    """Read a run manifest; raises ArtifactError when absent or malformed."""
    path = Path(run_dir) / MANIFEST
    if not path.exists():
        raise ArtifactError(f"no manifest.json in {run_dir}", run_dir=str(run_dir))
    try:
        payload = read_json(path)
    except Exception as exc:  # malformed JSON is a loud artifact error
        raise ArtifactError(f"manifest.json is not valid JSON: {exc}", run_dir=str(run_dir)) from exc
    if not isinstance(payload, dict):
        raise ArtifactError("manifest.json must be a JSON object", run_dir=str(run_dir))
    return payload


def load_run_config(run_dir: str | Path) -> dict[str, Any]:
    """Read the resolved config YAML of a run."""
    return read_yaml(Path(run_dir) / RESOLVED_CONFIG)


def summarize_run(run_dir: str | Path) -> RunSummary:
    """Build a RunSummary from manifest/metrics; never raises for missing metrics."""
    directory = Path(run_dir)
    manifest = load_run_manifest(directory)
    conditions = manifest.get("conditions") or {}
    summary = RunSummary(
        run_id=str(manifest.get("run_id") or directory.name),
        directory=directory,
        run_name=manifest.get("run_name"),
        experiment_id=manifest.get("experiment_id"),
        parent_experiment_id=manifest.get("parent_experiment_id"),
        model_id=(manifest.get("model") or {}).get("model_id"),
        config_hash=manifest.get("config_hash"),
        evidence_class=manifest.get("evidence_class"),
        conditions=dict(conditions) if isinstance(conditions, dict) else {},
        utc=manifest.get("utc"),
    )
    metrics_path = directory / METRICS
    if metrics_path.exists():
        metrics = read_json(metrics_path)
        if isinstance(metrics, dict):
            quality = metrics.get("quality") or {}
            summary.accuracy = quality.get("accuracy")
            summary.n_scored = metrics.get("n_scored")
            gate = metrics.get("release_gate") or {}
            summary.gate_status = gate.get("status")
    return summary


def iter_runs(root: str | Path) -> list[RunSummary]:
    """Every readable run under ``root`` (self-healing: skips non-run dirs)."""
    base = Path(root)
    if not base.exists():
        return []
    summaries: list[RunSummary] = []
    for child in sorted(p for p in base.iterdir() if p.is_dir()):
        if not (child / MANIFEST).exists():
            continue
        summaries.append(summarize_run(child))
    return summaries
