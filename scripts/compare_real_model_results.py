"""Compare every curated real-model result directory and check comparability.

Reads the generated ``summary.json`` of each model directory and writes
``comparison.json``/``comparison.md`` beside them. Numbers are never hand-edited: this
script is the only thing that should produce the cross-model table.

Usage:
    python3 scripts/compare_real_model_results.py results/colab_real_model
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:  # run from a checkout without an editable install
    sys.path.insert(0, str(ROOT / "src"))

SCHEMA_VERSION = "1.0"
#: Suites that must share one identity across models for a cross-model comparison.
COMPARABLE_SUITES = ("local_variance",)


def _load(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _suite(summary: dict[str, Any], suite: str) -> dict[str, Any]:
    return (summary.get("by_suite") or {}).get(suite) or {}


def _suite_runs(summary: dict[str, Any], suite: str) -> list[dict[str, Any]]:
    return [run for run in summary.get("runs") or [] if run.get("suite") == suite]


def _mean(summary: dict[str, Any], suite: str, field: str) -> Any:
    """Mean of one summary field across the runs of a suite, or None when not measured."""
    values = [run.get(field) for run in _suite_runs(summary, suite) if run.get(field) is not None]
    if not values:
        return None
    return sum(values) / len(values) if isinstance(values[0], (int, float)) else values[0]


def _gate(summary: dict[str, Any], suite: str) -> str:
    gates = {str(run.get("gate_status")) for run in _suite_runs(summary, suite) if run.get("gate_status")}
    return ", ".join(sorted(gates)) or "not evaluated"


def _latency(summary: dict[str, Any], suite: str) -> Any:
    values = [
        (run.get("metrics") or {}).get("latency_median")
        for run in summary.get("runs") or []
        if run.get("suite") == suite and (run.get("metrics") or {}).get("latency_median") is not None
    ]
    return round(sum(values) / len(values), 1) if values else None


def collect(root: Path) -> dict[str, Any]:
    """Collect one row per model directory and the cross-model identity check."""
    models = []
    for summary_path in sorted(root.glob("*/summary.json")):
        summary = _load(summary_path)
        if not summary:
            continue
        models.append({
            "directory": summary_path.parent.name,
            "models": summary["provenance"]["models"],
            "git_commits": summary["provenance"]["git_commits"],
            "evidence_modes": summary["provenance"]["evidence_modes"],
            "totals": summary["totals"],
            "core": {
                "runs": _suite(summary, "local_variance").get("n_runs"),
                "scored": _suite(summary, "local_variance").get("n_scored"),
                "quality_mean": _mean(summary, "local_variance", "quality_mean"),
                "distinct_quality_means": _suite(summary, "local_variance").get("distinct_quality_means"),
            },
            "rag_agent": {
                "runs": _suite(summary, "local_rag_agent").get("n_runs"),
                "quality_mean": _mean(summary, "local_rag_agent", "quality_mean"),
                "task_completion_rate": _mean(summary, "local_rag_agent", "task_completion_rate"),
            },
            "safety": {
                "runs": _suite(summary, "local_safety").get("n_runs"),
                "quality_mean": _mean(summary, "local_safety", "quality_mean"),
                "attack_success_rate": _mean(summary, "local_safety", "attack_success_rate"),
                "gate": _gate(summary, "local_safety"),
            },
            "latency_median_ms": {
                suite: _latency(summary, suite) for suite in ("local_variance", "local_rag_agent", "local_safety")
            },
            "suite_identities": summary.get("suite_identities") or {},
            "warnings": len(summary.get("warnings") or []),
        })
    identities: dict[str, dict[str, list[str]]] = {}
    for suite in COMPARABLE_SUITES:
        values: dict[str, set[str]] = {}
        for model in models:
            identity = (model["suite_identities"] or {}).get(suite) or {}
            for field in ("dataset_hashes", "task_hashes", "metric_definition_versions"):
                values.setdefault(field, set()).update(identity.get(field) or [])
        identities[suite] = {field: sorted(values.get(field) or []) for field in values}
    return {
        "schema_version": SCHEMA_VERSION,
        "source_root": str(root),
        "models": models,
        "comparable_suite_identities": identities,
    }


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Cross-model comparison",
        "",
        "Generated by `scripts/compare_real_model_results.py`; do not hand-edit.",
        "",
        "All models below ran the same suites under the same protocol. A higher mean is a higher",
        "observed mean, not a significant difference: the paired comparisons and confidence",
        "intervals in each model's `study/study_summary.json` carry that.",
        "",
        "## Results",
        "",
        "| model | runs | scored | core mean | distinct core means | RAG/agent mean | safety mean | attack success | safety gate | warnings |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    for model in sorted(payload["models"], key=lambda m: -(m["core"]["quality_mean"] or 0.0)):
        lines.append(
            "| `{model}` | {runs} | {scored} | {core} | {distinct} | {agent} | {safety} | {attack} | {gate} | {warnings} |".format(
                model="`, `".join(model["models"]) or model["directory"],
                runs=model["totals"]["n_runs"],
                scored=model["totals"]["n_scored_examples"],
                core=_fmt(model["core"]["quality_mean"]),
                distinct=model["core"]["distinct_quality_means"],
                agent=_fmt(model["rag_agent"]["quality_mean"]),
                safety=_fmt(model["safety"]["quality_mean"]),
                attack=_fmt(model["safety"]["attack_success_rate"]),
                gate=model["safety"]["gate"],
                warnings=model["warnings"],
            )
        )
    lines += [
        "",
        "## Comparability of the core suite",
        "",
        "Runs are comparable only when these identities match across every model; the model id and",
        "its revision are the intended difference.",
        "",
    ]
    for suite, identity in payload["comparable_suite_identities"].items():
        for field, values in identity.items():
            status = "OK" if len(values) == 1 else "MISMATCH"
            listed = ", ".join(value[:16] for value in values) or "none"
            lines.append(f"- `{suite}` {field}: {len(values)} distinct value(s) - {status} ({listed})")
    lines += [
        "",
        "## Reading this table",
        "",
        "- `distinct core means` counts different quality means inside the six-cell variance matrix.",
        "  A value of 1 means the seeds and prompt templates changed nothing, which is expected under",
        "  greedy decoding on a small frozen item set and is itself a finding, not a bug.",
        "- `attack success` and the safety gate are screening heuristics, not safety verdicts.",
        "- Latency is client-side wall-clock time on ephemeral Colab hardware.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path, nargs="?", default=ROOT / "results" / "colab_real_model")
    args = parser.parse_args()
    if not args.root.is_dir():
        parser.error(f"not a directory: {args.root}")
    payload = collect(args.root)
    (args.root / "comparison.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (args.root / "comparison.md").write_text(render_markdown(payload), encoding="utf-8")
    print(f"compared {len(payload['models'])} models; wrote {args.root / 'comparison.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
