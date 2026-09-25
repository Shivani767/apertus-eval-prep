"""Utilities for rebuilding reports and fingerprints from immutable run artifacts."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from apertus_eval_prep.core.artifacts import (
    FAILURE_FINGERPRINT,
    FAILURES,
    METRICS,
    REPORT_HTML,
    REPORT_MD,
    load_run_manifest,
)
from apertus_eval_prep.release.failures import failure_fingerprint, normalize_failure_records
from apertus_eval_prep.reporting.html import render_run_html
from apertus_eval_prep.reporting.markdown import render_run_markdown
from apertus_eval_prep.utils.serialization import read_json, read_jsonl, write_json, write_text

FORMATS = ("markdown", "html", "both")


def _read_optional(path: Path, default: Any) -> Any:
    return read_json(path) if path.exists() else default


def load_report_payload(run_dir: str | Path, *, baseline_run: str | Path | None = None) -> dict[str, Any]:
    """Load report inputs without rerunning the evaluation."""
    directory = Path(run_dir)
    manifest = load_run_manifest(directory)
    metrics = _read_optional(directory / METRICS, {})
    failures = normalize_failure_records(read_jsonl(directory / FAILURES), manifest=manifest)
    total = metrics.get("n_total")
    baseline_fingerprint = None
    if baseline_run is not None:
        baseline_dir = Path(baseline_run)
        baseline_fp_path = baseline_dir / FAILURE_FINGERPRINT
        if baseline_fp_path.exists():
            baseline_fingerprint = read_json(baseline_fp_path)
        else:
            baseline_fingerprint = failure_fingerprint(
                normalize_failure_records(read_jsonl(baseline_dir / FAILURES)),
                total=_read_optional(baseline_dir / METRICS, {}).get("n_total"),
            )
    fingerprint = failure_fingerprint(
        failures,
        total=total,
        conditions=manifest.get("conditions") or {},
        baseline_fingerprint=baseline_fingerprint,
    )
    return {
        "manifest": manifest,
        "metrics": metrics,
        "failures": failures,
        "failure_fingerprint": fingerprint,
        "baseline_run": str(baseline_run) if baseline_run is not None else None,
    }


def write_failure_fingerprint(
    run_dir: str | Path, *, baseline_run: str | Path | None = None
) -> tuple[Path, dict[str, Any]]:
    """Recompute and persist a run's failure fingerprint."""
    payload = load_report_payload(run_dir, baseline_run=baseline_run)
    target = Path(run_dir) / FAILURE_FINGERPRINT
    write_json(target, payload["failure_fingerprint"])
    return target, payload["failure_fingerprint"]


def write_run_reports(
    run_dir: str | Path, *, report_format: str = "both",
    output_dir: str | Path | None = None, baseline_run: str | Path | None = None,
) -> dict[str, Path | None]:
    """Render reports from an existing run; default output is the run directory."""
    if report_format not in FORMATS:
        raise ValueError(f"report_format must be one of {FORMATS}")
    payload = load_report_payload(run_dir, baseline_run=baseline_run)
    target = Path(output_dir or run_dir)
    paths: dict[str, Path | None] = {"markdown": None, "html": None}
    if report_format in {"markdown", "both"}:
        paths["markdown"] = write_text(target / REPORT_MD, render_run_markdown(payload))
    if report_format in {"html", "both"}:
        paths["html"] = write_text(target / REPORT_HTML, render_run_html(payload))
    return paths


__all__ = [
    "FORMATS", "load_report_payload", "write_failure_fingerprint", "write_run_reports",
]
