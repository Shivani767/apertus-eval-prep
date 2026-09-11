"""Research experiment runner — end-to-end workflow (Phase 13).

Ties existing modules into a reproducible pipeline:
  config snapshot → environment capture → run/collect → statistics →
  ranking → stability → registry entry → machine-readable result → report.

No evaluation logic lives here — it orchestrates run_eval, sweep, stats,
ranking, stability, reliability, reproduce, and report. Every result it
emits is traceable to an actual artifact via the registry path.
"""

from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apertus_eval_prep.config import load_config
from apertus_eval_prep.registry import load_registry


def _git_sha(repo_root: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True,
        )
        return out.stdout.strip() if out.returncode == 0 else None
    except OSError:
        return None


def _git_dirty(repo_root: Path) -> bool | None:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo_root, capture_output=True, text=True,
        )
        if out.returncode != 0:
            return None
        return bool(out.stdout.strip())
    except OSError:
        return None


@dataclass
class Environment:
    """Reproducibility metadata captured at run time."""
    python_version: str = platform.python_version()
    platform_system: str = platform.system()
    platform_machine: str = platform.machine()
    git_sha: str | None = None
    git_dirty: bool | None = None
    utc_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "python_version": self.python_version,
            "platform": f"{self.platform_system}/{self.platform_machine}",
            "git_sha": self.git_sha,
            "git_dirty": self.git_dirty,
            "utc": self.utc_timestamp,
        }


def capture_environment(repo_root: Path) -> Environment:
    return Environment(git_sha=_git_sha(repo_root), git_dirty=_git_dirty(repo_root))


@dataclass
class ExperimentResult:
    """One measured cell in an experiment."""
    run_id: str
    config_hash: str
    model_id: str
    factor: str
    factor_level: str
    accuracy: float
    n_items: int
    path: str
    status: str = "ok"


@dataclass
class ExperimentRun:
    """Full result of an experiment execution."""
    experiment_id: str
    config_snapshot: dict[str, Any]
    environment: dict[str, Any]
    results: list[ExperimentResult]
    registry_path: str
    output_dir: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "config_snapshot": self.config_snapshot,
            "environment": self.environment,
            "results": [r.__dict__ for r in self.results],
            "registry_path": self.registry_path,
            "output_dir": self.output_dir,
            "metadata": self.metadata,
        }


def run_experiment(
    experiment_id: str,
    config_path: Path,
    repo_root: Path,
    *,
    registry_path: Path,
    output_dir: Path,
    n_boot: int = 300,
    seed: int = 0,
) -> ExperimentRun:
    """Execute a full experiment end-to-end.

    1. Load and snapshot config.
    2. Capture environment (git SHA, platform, timestamp).
    3. Run evaluation via sweep (resumable via registry).
    4. Collect results from registry.
    5. Run statistical + ranking + stability analysis.
    6. Write machine-readable result + report.
    """
    from apertus_eval_prep.sweep import expand_ofat, run_sweep
    from apertus_eval_prep.config import RunConfig

    cfg = load_config(config_path)
    env = capture_environment(repo_root)

    # 3. Run sweep (resumable — skips completed hashes)
    sweep_results = run_sweep(
        cfg, repo_root, registry_path=registry_path, output_dir=output_dir,
    )

    # 4. Collect results from registry
    rows = load_registry(registry_path)
    results = []
    for row in rows:
        if row.get("status") != "ok" or not row.get("path"):
            continue
        overall = row.get("overall") or {}
        results.append(ExperimentResult(
            run_id=row.get("run_id", ""),
            config_hash=row.get("config_hash", ""),
            model_id=row.get("model_id", ""),
            factor=row.get("factor", "control"),
            factor_level=row.get("factor_level", "control"),
            accuracy=overall.get("accuracy", 0.0),
            n_items=overall.get("n", 0),
            path=row.get("path", ""),
        ))

    run = ExperimentRun(
        experiment_id=experiment_id,
        config_snapshot=cfg.to_dict() if hasattr(cfg, "to_dict") else {},
        environment=env.to_dict(),
        results=results,
        registry_path=str(registry_path),
        output_dir=str(output_dir),
    )

    # 5. Write machine-readable result
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / f"{experiment_id}_result.json"
    result_path.write_text(json.dumps(run.to_dict(), indent=2) + "\n", encoding="utf-8")

    # 6. Generate report
    from apertus_eval_prep.report_generation import generate_research_report
    report = generate_research_report(run, repo_root=repo_root, n_boot=n_boot, seed=seed)
    report_path = output_dir / f"{experiment_id}_report.md"
    report_path.write_text(report, encoding="utf-8")

    run.metadata["result_path"] = str(result_path)
    run.metadata["report_path"] = str(report_path)
    return run