"""Study-level aggregation over compatible completed run artifacts."""
from __future__ import annotations
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from apertus_eval_prep.core.artifacts import (
    CONFIDENCE_INTERVALS, FAILURE_FINGERPRINT, GATE_REPORT, MANIFEST, METRICS,
)
from apertus_eval_prep.core.errors import ArtifactError
from apertus_eval_prep.core.evidence import REAL_EVIDENCE_MODES, SYNTHETIC_EVIDENCE_MODES
from apertus_eval_prep.metrics.paired_comparison import paired_comparison
from apertus_eval_prep.metrics.robustness import robust_capability_score
from apertus_eval_prep.release.deployment import compare_deployment_configurations
from apertus_eval_prep.release.ingest import ingest_run_directory
from apertus_eval_prep.release.failures import failure_fingerprint
from apertus_eval_prep.review.ingest import review_evidence_for_runs
from apertus_eval_prep.study.compatibility import validate_study_compatibility
from apertus_eval_prep.study.schema import StudySpec
from apertus_eval_prep.utils.pii import redact_for_artifact
from apertus_eval_prep.utils.serialization import read_json, read_jsonl


def _review_summary(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {"status": "NOT_PROVIDED", "human_reviewed": False, "n_annotations": 0, "limitations": ["No completed review artifact was provided."]}
    try:
        payload = read_json(path)
    except (OSError, ValueError) as exc:
        raise ArtifactError(f"invalid review artifact: {path}") from exc
    if not isinstance(payload, Mapping):
        raise ArtifactError("review artifact must be a JSON object")
    return {"status": payload.get("human_review_status", "UNKNOWN"), "human_reviewed": bool(payload.get("human_reviewed", False)), "n_annotations": payload.get("n_annotations", len(payload.get("annotations", []))), "agreement": payload.get("agreement") or {}, "by_run": review_evidence_for_runs(payload), "limitations": list(payload.get("limitations") or [])}


def _fingerprint(run_dir: Path) -> dict[str, Any]:
    path = run_dir / FAILURE_FINGERPRINT
    if path.exists():
        return read_json(path)
    metrics = read_json(run_dir / METRICS) if (run_dir / METRICS).exists() else {}
    return failure_fingerprint(read_jsonl(run_dir / "failures.jsonl"), total=metrics.get("n_total"))


def _manifest(spec: StudySpec, run_ids: Sequence[str]) -> dict[str, Any]:
    return {"schema_version": "1.0", "study_id": spec.study_id, "study_title": spec.study_title, "research_question": spec.research_question, "hypothesis_ids": list(spec.hypothesis_ids), "planned_sample_counts": dict(spec.planned_sample_counts), "protocol_path": spec.protocol_path, "preregistration_path": spec.preregistration_path, "deviation_log_path": spec.deviation_log_path, "evidence_mode": spec.evidence_mode, "config_hash": spec.config_hash(), "run_ids": list(run_ids), "generated_at": datetime.now(timezone.utc).isoformat()}


def analyze_study(spec: StudySpec, run_dirs: Sequence[str | Path], *, reviews: str | Path | None = None) -> dict[str, Any]:
    if not run_dirs:
        raise ArtifactError("at least one run directory is required")
    required = (MANIFEST, METRICS, CONFIDENCE_INTERVALS, GATE_REPORT, FAILURE_FINGERPRINT)
    missing = {
        str(path): [name for name in required if not (Path(path) / name).exists()]
        for path in run_dirs
    }
    missing = {path: names for path, names in missing.items() if names}
    if missing:
        raise ArtifactError("study runs are missing required artifacts", missing=missing, required=list(required))
    points = [ingest_run_directory(path) for path in run_dirs]
    compatibility = validate_study_compatibility(
        points, expected_study_id=spec.study_id, expected_evidence_mode=spec.evidence_mode
    )
    modes = sorted({str(p.get("evidence_mode") or "UNKNOWN") for p in points})
    fixture_shaped = all(
        "fixture" in str(p.get("model_id") or "").lower()
        or any("fixture" in str(x).lower() for x in (p.get("known_limitations") or []))
        for p in points
    )
    synthetic_only = fixture_shaped or (bool(modes) and all(m in SYNTHETIC_EVIDENCE_MODES for m in modes))
    real_evidence = any(m in REAL_EVIDENCE_MODES for m in modes) and not fixture_shaped
    pareto = compare_deployment_configurations(points)
    review = _review_summary(reviews)
    rows = []
    for path, point in zip(run_dirs, points):
        directory = Path(path)
        metrics = read_json(directory / METRICS)
        ci_path = directory / CONFIDENCE_INTERVALS
        gate_path = directory / GATE_REPORT
        rows.append({
            "run_id": point.get("run_id"), "run_directory": str(directory), "label": point.get("label"),
            "evidence_mode": point.get("evidence_mode"), "model_id": point.get("model_id"),
            "model_revision": point.get("model_revision"), "config_hash": point.get("config_hash"),
            "dataset_hash": point.get("dataset_hash"), "prompt_hash": point.get("prompt_hash"),
            "quality": metrics.get("quality"), "confidence_intervals": read_json(ci_path) if ci_path.exists() else metrics.get("confidence_intervals"),
            "deployment": point, "system": metrics.get("system"), "safety": metrics.get("safety"),
            "release_gate": read_json(gate_path) if gate_path.exists() else metrics.get("release_gate"),
            "failure_fingerprint": _fingerprint(directory),
            "human_reviewed": bool(review.get("by_run", {}).get(str(point.get("run_id")), False)),
        })
    quality_means = [
        (row.get("quality") or {}).get("mean") for row in rows
        if (row.get("quality") or {}).get("mean") is not None
    ]
    rcs = robust_capability_score(
        quality_means,
        lambda_=float(spec.comparison.get("robust_capability_lambda", 1.0)),
    )
    comparisons = []
    if rows:
        base = rows[0]
        base_scores = {str(x.get("example_id")): x.get("score") for x in read_jsonl(Path(base["run_directory"]) / "scored_examples.jsonl")}
        for candidate in rows[1:]:
            candidate_scores = {str(x.get("example_id")): x.get("score") for x in read_jsonl(Path(candidate["run_directory"]) / "scored_examples.jsonl")}
            if base_scores and candidate_scores:
                paired = paired_comparison(
                    base_scores, candidate_scores,
                    practical_effect_threshold=float(spec.comparison.get("practical_effect_threshold", 0.02)),
                    min_sample_size=int(spec.comparison.get("min_sample_size", 20)),
                    n_boot=int(spec.comparison.get("n_boot", 400)),
                    alpha=float(spec.comparison.get("alpha", 0.05)),
                    seed=int(spec.comparison.get("seed", 0)),
                )
            else:
                paired = {"status": "INCONCLUSIVE", "delta": None, "n_paired": 0,
                          "limitations": ["no aligned scored examples"]}
            comparisons.append({
                "baseline_run": base.get("run_id"), "candidate_run": candidate.get("run_id"),
                "quality_delta": paired.get("delta"), "status": paired.get("status"),
                "ci_low": paired.get("ci_low"), "ci_high": paired.get("ci_high"),
                "effect_size": paired.get("effect_size"), "n_paired": paired.get("n_paired"),
                "practically_meaningful": (
                    abs(float(paired["delta"])) >= float(spec.comparison.get("practical_effect_threshold", 0.02))
                    if paired.get("delta") is not None else False
                ),
            })
    limitations = ["No causal conclusions are drawn from observed configuration differences.", "RCS is experimental and is not a standard universal metric.", "Human-review agreement measures consistency, not correctness or safety validity."]
    if fixture_shaped:
        limitations.insert(0, "Run artifacts are fixture-shaped; no real-model execution is evidenced.")
    elif synthetic_only:
        limitations.insert(0, "No real-model evidence is available; this report is framework/synthetic validation only.")
    summary = {"schema_version": "1.0", "study": spec.to_dict(), "manifest": _manifest(spec, [str(r.get("run_id")) for r in rows]), "compatibility": compatibility, "evidence_modes": modes, "real_model_evidence_available": real_evidence and not synthetic_only, "synthetic_or_mock": synthetic_only, "rows": rows, "comparisons": comparisons, "robust_capability_score": rcs, "pareto": pareto, "review": review, "deviations": {"status": "NOT_ASSESSED", "path": spec.deviation_log_path, "note": "Record and review deviations against the preregistration before publication."}, "limitations": limitations}
    return redact_for_artifact(summary)


__all__ = ["analyze_study"]
