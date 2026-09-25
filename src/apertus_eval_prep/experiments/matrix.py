"""Deterministic experiment-matrix orchestration on the typed platform."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from apertus_eval_prep.core.config import expand_experiment, load_experiment_spec
from apertus_eval_prep.core.errors import PlatformError
from apertus_eval_prep.core.runner import RunResult, run_evaluation
from apertus_eval_prep.metrics.aggregate import summarize_scores
from apertus_eval_prep.metrics.confidence_intervals import bootstrap_mean_ci
from apertus_eval_prep.metrics.paired_comparison import paired_comparison
from apertus_eval_prep.metrics.robustness import analyze_condition_sensitivity, robust_capability_score
from apertus_eval_prep.utils.pii import (
    redact_for_artifact,
    redact_text_for_artifact,
    redact_text_for_report,
)
from apertus_eval_prep.utils.serialization import read_jsonl, write_json, write_text
from apertus_eval_prep.experiments.reporting import render_experiment_html, render_experiment_markdown


@dataclass
class MatrixCell:
    cell_id: str
    conditions: dict[str, Any]
    is_baseline: bool
    status: str = "pending"
    run_id: str | None = None
    directory: str | None = None
    mean_quality: float | None = None
    n_scored: int | None = None
    n_total: int | None = None
    n_failed: int | None = None
    config_hash: str | None = None
    parent_experiment_id: str | None = None
    resolved_config_path: str | None = None
    evidence_class: str | None = None
    confidence_interval: dict[str, Any] | None = None
    error: str | None = None
    example_scores: dict[str, float] = field(default_factory=dict)
    example_correct: dict[str, bool] = field(default_factory=dict)


@dataclass
class MatrixResult:
    experiment_id: str
    cells: list[MatrixCell] = field(default_factory=list)
    report: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"experiment_id": self.experiment_id, "cells": [c.__dict__ for c in self.cells], "report": self.report}


def run_experiment_matrix(
    config_path: str | Path,
    repo_root: str | Path,
    *,
    output_root: str | Path | None = None,
    command: str | None = None,
) -> MatrixResult:
    """Expand and execute a matrix; unavailable cells are reported, not hidden."""
    spec = load_experiment_spec(config_path)
    cells = expand_experiment(spec)
    result = MatrixResult(spec.experiment_id)
    for planned in cells:
        cell = MatrixCell(planned.cell_id, dict(planned.conditions), planned.is_baseline)
        try:
            run: RunResult = run_evaluation(
                planned.run_spec, repo_root, output_root=output_root, command=command
            )
            quality = run.metrics.get("quality") or {}
            cell.status = "ok"
            cell.run_id = run.run_id
            cell.directory = str(run.directory)
            cell.mean_quality = quality.get("mean")
            cell.n_scored = quality.get("n_scored")
            cell.n_total = run.metrics.get("n_total")
            cell.n_failed = run.metrics.get("n_failed")
            cell.config_hash = run.manifest.get("config_hash")
            cell.parent_experiment_id = run.manifest.get("parent_experiment_id")
            cell.resolved_config_path = str(run.directory / "config.resolved.yaml")
            cell.evidence_class = run.manifest.get("evidence_class")
            cell.confidence_interval = (run.metrics.get("confidence_intervals") or {}).get("quality_mean")
            for row in read_jsonl(Path(run.directory) / "scored_examples.jsonl"):
                if isinstance(row, dict) and row.get("score") is not None:
                    example_id = str(row.get("example_id"))
                    cell.example_scores[example_id] = float(row["score"])
                    cell.example_correct[example_id] = bool(row.get("correct"))
        except Exception as exc:  # cell isolation is intentional for research matrices
            cell.status = "error"
            cell.error = redact_text_for_artifact(f"{type(exc).__name__}: {exc}")
        result.cells.append(cell)
    result.report = analyze_matrix_cells(result.cells, spec.comparison.to_dict(), config_path=str(config_path))
    result.report["parent_experiment_id"] = spec.experiment_id
    result.report["config_path"] = str(config_path)
    if output_root is not None:
        report_path = Path(output_root).resolve() / f"{spec.experiment_id}.experiment.json"
        result.report["report_path"] = str(report_path)
        result.report["markdown_path"] = str(report_path.with_suffix(".md"))
        result.report["html_path"] = str(report_path.with_suffix(".html"))
        payload = redact_for_artifact(result.to_dict())
        write_json(report_path, payload)
        write_text(report_path.with_suffix(".md"), redact_text_for_report(render_experiment_markdown(payload)))
        write_text(report_path.with_suffix(".html"), redact_text_for_report(render_experiment_html(payload)))
    return result


def _example_rows(cells: list[MatrixCell]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cell in cells:
        for example_id, score in sorted(cell.example_scores.items()):
            rows.append({
                "cell_id": cell.cell_id,
                "example_id": example_id,
                "score": score,
                "correct": cell.example_correct.get(example_id, score >= 0.5),
                **cell.conditions,
            })
    return rows


def analyze_matrix_cells(
    cells: list[MatrixCell], comparison: dict[str, Any] | None = None,
    *, config_path: str = "<experiment-config>"
) -> dict[str, Any]:
    """Aggregate cells, compare aligned examples, and rank condition instability."""
    comparison = dict(comparison or {})
    ok = [cell for cell in cells if cell.status == "ok"]
    scored_cells = [cell for cell in ok if cell.mean_quality is not None]
    baseline = next((cell for cell in scored_cells if cell.is_baseline), None)
    candidate = next((cell for cell in scored_cells if not cell.is_baseline), None)
    rows = _example_rows(ok)
    factors = sorted({factor for cell in ok for factor in cell.conditions})
    n_boot = int(comparison.get("n_boot", 400))
    seed = int(comparison.get("seed", 0))
    factor_metrics = analyze_condition_sensitivity(
        rows, factors, n_boot=n_boot, seed=seed
    )
    cell_means = [float(cell.mean_quality) for cell in scored_cells if cell.mean_quality is not None]
    cell_mean_ci = bootstrap_mean_ci(cell_means, n_boot=n_boot, alpha=float(comparison.get("alpha", 0.05)), seed=seed)
    comparison_report = None
    if baseline is not None and candidate is not None:
        if baseline.example_scores and candidate.example_scores:
            comparison_report = paired_comparison(
                baseline.example_scores,
                candidate.example_scores,
                n_boot=n_boot,
                alpha=float(comparison.get("alpha", 0.05)),
                seed=seed,
                practical_effect_threshold=float(comparison.get("practical_effect_threshold", 0.02)),
                min_sample_size=int(comparison.get("min_sample_size", 20)),
                safety_critical=bool(comparison.get("safety_critical", False)),
            )
        else:
            comparison_report = {
                "baseline_mean": baseline.mean_quality,
                "candidate_mean": candidate.mean_quality,
                "delta": None, "ci_low": None, "ci_high": None,
                "n_paired": 0, "status": "INCONCLUSIVE",
                "limitations": ["no aligned per-example scores"],
            }
    quality_summary = summarize_scores(
        cell_means,
        total=len(cells),
        failed=sum(cell.status == "error" for cell in cells),
    )
    quality_summary["confidence_interval"] = cell_mean_ci
    rcs = robust_capability_score(
        cell_means,
        lambda_=float(comparison.get("robust_capability_lambda", comparison.get("lambda", 1.0))),
    )
    return {
        "experiment_summary": {
            "n_cells": len(cells), "n_ok": len(ok),
            "n_error": sum(c.status == "error" for c in cells),
            "n_evaluated": len(scored_cells),
            "n_examples": len(rows),
        },
        "quality_summary": quality_summary,
        "factor_metrics": factor_metrics,
        "confidence_intervals": {
            "cell_quality_mean": cell_mean_ci,
            "per_cell": {cell.cell_id: cell.confidence_interval for cell in scored_cells},
        },
        "robust_capability_score": rcs,
        "baseline_cell": baseline.cell_id if baseline else None,
        "candidate_cell": candidate.cell_id if candidate else None,
        "baseline_vs_first_candidate": comparison_report,
        "unstable_conditions": factor_metrics.get("unstable_conditions", []),
        "representative_sensitive_failures": factor_metrics.get("representative_sensitive_failures", []),
        "cells": [cell.__dict__ for cell in cells],
        "parent_experiment_id": None,
        "reproduction_command": f"apertus-eval-prep platform-matrix --config {config_path}",
        "limitations": [
            "Synthetic/mock cells are evidence of platform behavior, not model quality",
            "RCS is an experimental project-defined score, not a universal benchmark metric",
            "Small or incomplete matrices should be interpreted as inconclusive",
        ],
    }


# Short alias used by extension authors.
run_matrix = run_experiment_matrix

__all__ = ["MatrixCell", "MatrixResult", "run_experiment_matrix", "run_matrix", "analyze_matrix_cells"]
