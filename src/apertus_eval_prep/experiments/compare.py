"""Comparison of two immutable platform run directories."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apertus_eval_prep.core.artifacts import summarize_run
from apertus_eval_prep.metrics.paired_comparison import paired_comparison
from apertus_eval_prep.release.failures import failure_fingerprint, normalize_failure_records
from apertus_eval_prep.utils.serialization import read_json, read_jsonl, write_json


def compare_run_directories(baseline: str | Path, candidate: str | Path, *, output: str | Path | None = None) -> dict[str, Any]:
    """Compare aligned per-example scores and emit an auditable summary."""
    left, right = Path(baseline), Path(candidate)
    a = {str(row.get("example_id")): row for row in read_jsonl(left / "scored_examples.jsonl") if isinstance(row, dict)}
    b = {str(row.get("example_id")): row for row in read_jsonl(right / "scored_examples.jsonl") if isinstance(row, dict)}
    ids = sorted(set(a) & set(b))
    left_failures = normalize_failure_records(read_jsonl(left / "failures.jsonl"))
    right_failures = normalize_failure_records(read_jsonl(right / "failures.jsonl"))
    left_metrics = read_json(left / "metrics.json") if (left / "metrics.json").exists() else {}
    right_metrics = read_json(right / "metrics.json") if (right / "metrics.json").exists() else {}
    left_fingerprint = failure_fingerprint(left_failures, total=left_metrics.get("n_total"))
    right_fingerprint = failure_fingerprint(
        right_failures, total=right_metrics.get("n_total"), baseline_fingerprint=left_fingerprint
    )
    result = {
        "baseline": summarize_run(left).to_dict(), "candidate": summarize_run(right).to_dict(),
        "paired": paired_comparison([a[i].get("score") for i in ids], [b[i].get("score") for i in ids],
                                    baseline_ids=ids, candidate_ids=ids, min_sample_size=1),
        "n_aligned": len(ids), "n_missing_baseline": sorted(set(b) - set(a)),
        "n_missing_candidate": sorted(set(a) - set(b)),
        "failure_fingerprints": {"baseline": left_fingerprint, "candidate": right_fingerprint},
        "evidence_note": "Comparison preserves each run's evidence class; mock results are not real benchmark evidence.",
    }
    if output is not None:
        write_json(output, result)
    return result


def comparison_markdown(result: dict[str, Any]) -> str:
    paired = result.get("paired") or {}
    lines = ["# Baseline vs candidate", "", f"- Aligned examples: `{result.get('n_aligned', 0)}`",
             f"- Delta (candidate - baseline): `{paired.get('delta')}`",
             f"- 95% bootstrap interval: `[{paired.get('ci_low')}, {paired.get('ci_high')}]`",
             f"- Classification: **{paired.get('status', 'INCONCLUSIVE')}**", "",
             "## Missing observations", "",
             f"- Missing from baseline: `{result.get('n_missing_baseline', [])}`",
             f"- Missing from candidate: `{result.get('n_missing_candidate', [])}`", "",
             result.get("evidence_note", "")]
    return "\n".join(lines) + "\n"


__all__ = ["compare_run_directories", "comparison_markdown"]
