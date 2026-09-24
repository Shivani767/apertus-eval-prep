"""Run provenance: the record that makes an artifact auditable.

A manifest answers, without ambiguity: which code, which environment, which
model revision, which dataset bytes, which prompt template, which config, and
which command produced these numbers.
"""

from __future__ import annotations

import platform as _platform
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apertus_eval_prep.core.schemas import RunSpec
from apertus_eval_prep.core.evidence import normalize_evidence
from apertus_eval_prep.utils.environment import (
    git_metadata, hardware_metadata, package_versions, platform_metadata, python_metadata,
)
from apertus_eval_prep.utils.runtime_profile import profile_runtime
from apertus_eval_prep.utils.hashing import hash_dataset, hash_file, hash_prompt, hash_task
from apertus_eval_prep.utils.pii import redact_for_artifact, redact_text_for_artifact

#: Bump when the artifact layout changes in a way readers must know about.
ARTIFACT_FORMAT_VERSION = "1.0.0"

DEFAULT_PACKAGES: tuple[str, ...] = (
    "apertus-eval-prep",
    "torch",
    "transformers",
    "vllm",
    "pyyaml",
    "pytest",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class DatasetLock:
    """Byte-level identity of the dataset slice actually evaluated."""

    path: str
    hash: str
    n_examples: int | None = None
    tasks: list[str] = field(default_factory=list)
    split: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "hash": self.hash,
            "id": self.id or self.hash,
            "hash_algorithm": "sha256-16",
            "n_examples": self.n_examples,
            "tasks": list(self.tasks),
            "split": self.split,
            **self.extra,
        }


def build_dataset_lock(
    path: str | Path,
    *,
    tasks: list[str] | None = None,
    split: str | None = None,
    n_examples: int | None = None,
    extra: dict[str, Any] | None = None,
) -> DatasetLock:
    """Hash a dataset file; raises FileNotFoundError when the slice is missing."""
    dataset_path = Path(path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"dataset not found: {dataset_path}")
    return DatasetLock(
        path=str(path),
        hash=hash_dataset(dataset_path),
        id=hash_dataset(dataset_path),
        n_examples=n_examples,
        tasks=list(tasks or []),
        split=split,
        extra=dict(extra or {}),
    )


def prompt_template_hash(run_spec: RunSpec, repo_root: str | Path | None = None) -> str:
    """Hash the prompt protocol, resolving few-shot files against the repo root."""
    payload = run_spec.prompt.template_payload()
    if run_spec.prompt.fewshot_path:
        fewshot = Path(run_spec.prompt.fewshot_path)
        if not fewshot.is_absolute() and repo_root is not None:
            fewshot = Path(repo_root) / fewshot
        if fewshot.exists():
            payload += f"\nfewshot_sha256_16={hash_file(fewshot)}"
        else:
            payload += "\nfewshot_missing=1"
    return hash_prompt(payload)


def build_run_manifest(
    run_spec: RunSpec,
    *,
    run_id: str,
    repo_root: str | Path | None,
    command: str | None,
    dataset_lock: DatasetLock | None,
    template_hash: str | None = None,
    config_hash: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the immutable manifest for one run.

    Git metadata is ``available: false`` (never an exception) when git is absent,
    so the platform works from a tarball or a container without git installed.
    """
    root = Path(repo_root) if repo_root is not None else None
    git = git_metadata(root) if root is not None else git_metadata(None)
    task_payload = run_spec.task.to_dict()
    task_id = hash_task(task_payload)
    task_hash = hash_task({
        "kind": run_spec.task.kind,
        "path": run_spec.task.path,
        "tasks": list(run_spec.task.tasks),
        "split": run_spec.task.split,
        "limit": run_spec.task.limit,
        "episode_ids": list(run_spec.task.episode_ids),
        "perturbations": list(run_spec.task.perturbations),
    })
    dataset_payload = dataset_lock.to_dict() if dataset_lock is not None else None
    prompt_version = run_spec.prompt.version or run_spec.prompt.prompt_id or "unversioned"
    prompt_hash = template_hash or prompt_template_hash(run_spec, root)
    resolved_config_hash = config_hash or run_spec.config_hash()
    evidence = normalize_evidence(
        run_spec.evidence.to_dict(), legacy_class=run_spec.evidence_class, adapter_kind=run_spec.adapter.kind
    )
    runtime_profile = profile_runtime(
        device=run_spec.runtime.device, precision=run_spec.runtime.precision,
        quantization=run_spec.runtime.quantization,
        include_torch=evidence["mode"] in {"LOCAL_REAL_MODEL", "HARDWARE_MEASURED"},
    )
    manifest = {
        "artifact_format_version": ARTIFACT_FORMAT_VERSION,
        "run_id": run_id,
        "run_name": run_spec.run_name,
        "experiment_id": run_spec.experiment_id,
        "parent_experiment_id": run_spec.parent_experiment_id,
        "utc": utc_now(),
        "entrypoint": command,
        "command": command,
        "entrypoint_command": command,
        "tags": list(run_spec.tags),
        "config_hash": resolved_config_hash,
        "resolved_config_hash": resolved_config_hash,
        "dataset_id": dataset_payload.get("id") if dataset_payload else None,
        "dataset_hash": dataset_payload.get("hash") if dataset_payload else None,
        "task_id": task_id,
        "task_kind": run_spec.task.kind,
        "task_hash": task_hash,
        "task": {
            "id": task_id,
            "kind": run_spec.task.kind,
            "path": run_spec.task.path,
            "tasks": list(run_spec.task.tasks),
            "split": run_spec.task.split,
            "limit": run_spec.task.limit,
            "hash": task_hash,
        },
        "prompt": {
            "prompt_id": run_spec.prompt.prompt_id,
            "version": prompt_version,
            "prompt_hash": prompt_hash,
            "template_hash": prompt_hash,
            "fewshot_path": run_spec.prompt.fewshot_path,
            "system_prompt_present": bool(run_spec.prompt.system_prompt),
        },
        "dataset": dataset_payload,
        "model_id": run_spec.adapter.model_id,
        "model_revision": run_spec.adapter.revision,
        "model": {
            "model_id": run_spec.adapter.model_id,
            "model_revision": run_spec.adapter.revision,
            "tokenizer_id": run_spec.adapter.params.get("tokenizer_id", run_spec.adapter.model_id),
            "tokenizer_revision": run_spec.adapter.params.get("tokenizer_revision", run_spec.adapter.revision),
            "adapter_kind": run_spec.adapter.kind,
            "adapter_name": run_spec.adapter.name,
        },
        "backend": {
            "device": run_spec.runtime.device,
            "precision": run_spec.runtime.precision,
            "quantization": run_spec.runtime.quantization,
            "batch_size": run_spec.runtime.batch_size,
        },
        "decoding": run_spec.decoding.to_dict(),
        "seed": run_spec.decoding.seed,
        "random_seed": run_spec.decoding.seed,
        "dimensions": run_spec.dimensions.to_dict(),
        "conditions": dict(run_spec.conditions),
        "evidence_class": run_spec.evidence_class,
        "evidence_mode": evidence["mode"],
        "evidence": evidence,
        "cost": run_spec.cost.to_dict(),
        "metric_definition_version": "1.0",
        "runtime_profile": runtime_profile,
        "git_commit": git.get("commit"),
        "git_dirty": git.get("dirty"),
        "git": git,
        "environment": {
            "python": python_metadata(),
            "platform": platform_metadata(),
            "platform_string": _platform.platform(),
            "hardware": hardware_metadata(
                include_torch=evidence["mode"] in {"LOCAL_REAL_MODEL", "HARDWARE_MEASURED"}
            ),
            "packages": package_versions(DEFAULT_PACKAGES),
        },
        "extra": dict(extra or {}),
    }
    # Provenance is an artifact boundary: redact credentials even when a caller
    # disabled PII redaction for raw prompt/output review.
    safe_command = None if command is None else redact_text_for_artifact(command)
    manifest["entrypoint"] = safe_command
    manifest["command"] = safe_command
    manifest["entrypoint_command"] = safe_command
    return redact_for_artifact(manifest)
