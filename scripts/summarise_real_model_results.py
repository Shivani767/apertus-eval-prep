"""Summarise curated Colab real-model run artifacts into summary.json/summary.md.

Usage:
    python3 scripts/summarise_real_model_results.py results/colab_real_model/Qwen2.5-3B-Instruct

The run tree is the immutable record. This script only reads it (``manifest.json``,
``metrics.json``, ``gate_report.json`` and friends) and writes two derived files beside
it. Numbers are never hand-edited, and anything questionable is reported as a warning
rather than hidden. A missing or malformed artifact yields an empty value, never a
fabricated one.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

SCHEMA_VERSION = "1.0"

#: Revisions that do not identify a reproducible model snapshot.
UNPINNED_REVISIONS = {"", "main", "master", "latest", "none", "OPTIONAL_PINNED_REVISION"}

#: Suite directory whose runs are expected to carry a non-real evidence mode.
MOCK_SUITE = "mock_smoke"


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object; return {} when the file is missing or not an object."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def run_directories(root: Path) -> list[Path]:
    """Every run directory below root (a directory holding manifest.json)."""
    found = {path.parent for path in root.rglob("manifest.json")}
    return sorted(found, key=lambda path: str(path.relative_to(root)))


def summarise_run(run_dir: Path, root: Path) -> dict[str, Any]:
    """Project one run directory onto the fields the summary reports."""
    manifest = read_json(run_dir / "manifest.json")
    metrics = read_json(run_dir / "metrics.json")
    quality = metrics.get("quality") or {}
    latency = metrics.get("latency") or {}
    gate = read_json(run_dir / "gate_report.json")
    model = manifest.get("model") or {}
    evidence = manifest.get("evidence") or {}
    relative = run_dir.relative_to(root)
    return {
        "suite": relative.parts[0] if len(relative.parts) > 1 else "(root)",
        "run_directory": str(relative),
        "run_id": manifest.get("run_id") or run_dir.name,
        "experiment_id": manifest.get("experiment_id"),
        "model_id": model.get("model_id") or manifest.get("model_id"),
        "model_revision": model.get("model_revision") or manifest.get("model_revision"),
        "tokenizer_id": model.get("tokenizer_id"),
        "evidence_mode": evidence.get("mode") or manifest.get("evidence_mode"),
        "real_model_execution": evidence.get("real_model_execution"),
        "runtime_environment": evidence.get("runtime_environment"),
        "git_commit": manifest.get("git_commit"),
        "git_dirty": manifest.get("git_dirty"),
        "dataset_hash": manifest.get("dataset_hash"),
        "task_hash": manifest.get("task_hash"),
        "metric_definition_version": manifest.get("metric_definition_version"),
        "config_hash": manifest.get("config_hash"),
        "conditions": manifest.get("conditions") or {},
        "n_total": metrics.get("n_total"),
        "n_scored": quality.get("n_scored"),
        "n_failed": quality.get("n_failed"),
        "quality_mean": quality.get("mean"),
        "latency_median_ms": latency.get("median"),
        "gate_status": gate.get("status"),
        "gate_reasons": list(gate.get("reasons") or []),
    }


def condition_label(conditions: dict[str, Any]) -> str:
    """Render the configuration conditions that matter for reading a run."""
    keys = ("prompt_template", "seed", "precision", "quantization", "backend")
    parts = [f"{key}={conditions[key]}" for key in keys if conditions.get(key) is not None]
    return ", ".join(parts) or "-"


def build_summary(root: Path) -> dict[str, Any]:
    """Build the whole-tree summary, including warnings about weak evidence."""
    runs = [summarise_run(run_dir, root) for run_dir in run_directories(root)]
    real_runs = [run for run in runs if run["evidence_mode"] == "LOCAL_REAL_MODEL"]
    mock_runs = [run for run in runs if run["evidence_mode"] != "LOCAL_REAL_MODEL"]
    datasets = sorted({str(run["dataset_hash"]) for run in real_runs if run["dataset_hash"]})
    tasks = sorted({str(run["task_hash"]) for run in real_runs if run["task_hash"]})
    metric_versions = sorted(
        {str(run["metric_definition_version"]) for run in real_runs if run["metric_definition_version"]}
    )

    warnings: list[str] = []
    unpinned = sorted(
        {str(run["model_revision"] or "") for run in real_runs if str(run["model_revision"] or "") in UNPINNED_REVISIONS}
    )
    if unpinned:
        warnings.append(
            f"{len(real_runs)} real-model runs record revision(s) {unpinned}, which are not pinned commits; "
            "the model snapshot is not reproducible from the manifest alone"
        )
    stray = [run for run in mock_runs if run["suite"] != MOCK_SUITE]
    if stray:
        warnings.append(f"non-real evidence outside {MOCK_SUITE}/: {[run['run_directory'] for run in stray]}")

    by_suite: dict[str, dict[str, Any]] = {}
    suite_identities: dict[str, dict[str, list[str]]] = {}
    for suite in sorted({run["suite"] for run in runs}):
        suite_runs = [run for run in runs if run["suite"] == suite]
        suite_real = [run for run in suite_runs if run["evidence_mode"] == "LOCAL_REAL_MODEL"]
        qualities = [float(run["quality_mean"]) for run in suite_runs if run["quality_mean"] is not None]
        distinct = len({round(value, 12) for value in qualities})
        by_suite[suite] = {
            "n_runs": len(suite_runs),
            "n_scored": sum(int(run["n_scored"] or 0) for run in suite_runs),
            "quality_mean_of_runs": mean(qualities) if qualities else None,
            "distinct_quality_means": distinct,
            "gate_statuses": dict(Counter(str(run["gate_status"]) for run in suite_runs)),
        }
        suite_identities[suite] = {
            "dataset_hashes": sorted({str(run["dataset_hash"]) for run in suite_real if run["dataset_hash"]}),
            "task_hashes": sorted({str(run["task_hash"]) for run in suite_real if run["task_hash"]}),
            "metric_definition_versions": sorted(
                {str(run["metric_definition_version"]) for run in suite_real if run["metric_definition_version"]}
            ),
        }
        for field, values in suite_identities[suite].items():
            if len(values) > 1:
                warnings.append(
                    f"{suite}: runs span {len(values)} distinct {field} values; "
                    "pair only runs that share an identical identity"
                )
        if suite in {"local_variance", "local_rag_agent"} and len(qualities) > 1 and distinct == 1:
            warnings.append(
                f"{suite}: all {len(qualities)} configurations scored exactly {qualities[0]:.4f}; "
                "the matrix produced no observed configuration variance"
            )
    for run in runs:
        status = str(run["gate_status"] or "")
        if status.startswith("BLOCKED"):
            reasons = run["gate_reasons"]
            shown = "; ".join(reasons[:3]) + (f" (+{len(reasons) - 3} more)" if len(reasons) > 3 else "")
            warnings.append(f"{run['run_id'].split('-')[0]} ({run['suite']}): gate {status} -> {shown}")

    return {
        "schema_version": SCHEMA_VERSION,
        "source_root": str(root),
        "provenance": {
            "models": sorted({f"{run['model_id']}@{run['model_revision']}" for run in real_runs if run["model_id"]}),
            "tokenizers": sorted({str(run["tokenizer_id"]) for run in real_runs if run["tokenizer_id"]}),
            "evidence_modes": sorted({str(run["evidence_mode"]) for run in runs}),
            "runtime_environments": sorted(
                {str(run["runtime_environment"]) for run in real_runs if run["runtime_environment"]}
            ),
            "git_commits": sorted({str(run["git_commit"]) for run in runs if run["git_commit"]}),
            "any_git_dirty": any(bool(run["git_dirty"]) for run in runs),
            "dataset_hashes": datasets,
            "task_hashes": tasks,
            "metric_definition_versions": metric_versions,
        },
        "totals": {
            "n_runs": len(runs),
            "n_real_runs": len(real_runs),
            "n_non_real_runs": len(mock_runs),
            "n_scored_examples": sum(int(run["n_scored"] or 0) for run in runs),
        },
        "by_suite": by_suite,
        "suite_identities": suite_identities,
        "runs": runs,
        "warnings": warnings,
    }


def _format(value: Any, digits: int = 4) -> str:
    """Render a value for a Markdown table, using '-' for unknown values."""
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def render_markdown(summary: dict[str, Any]) -> str:
    """Render the summary as human-readable Markdown."""
    provenance = summary["provenance"]
    totals = summary["totals"]
    lines = [
        "# Colab real-model run summary",
        "",
        "Generated by `scripts/summarise_real_model_results.py`; do not hand-edit.",
        "",
        "## Totals",
        "",
        f"- runs: **{totals['n_runs']}** ({totals['n_real_runs']} real-model, {totals['n_non_real_runs']} mock/fixture)",
        f"- scored examples: **{totals['n_scored_examples']}**",
        "",
        "## Provenance",
        "",
        f"- models: {', '.join(f'`{m}`' for m in provenance['models']) or '-'}",
        f"- tokenizers: {', '.join(f'`{t}`' for t in provenance['tokenizers']) or '-'}",
        f"- evidence modes: {', '.join(provenance['evidence_modes']) or '-'}",
        f"- runtime: {', '.join(provenance['runtime_environments']) or '-'}",
        f"- git commit(s): {', '.join(provenance['git_commits']) or '-'}"
        + (" (dirty working tree)" if provenance["any_git_dirty"] else ""),
        f"- dataset hash(es): {', '.join(h[:16] for h in provenance['dataset_hashes']) or '-'}",
        f"- task hash(es): {', '.join(h[:16] for h in provenance['task_hashes']) or '-'}",
        f"- metric definition version(s): {', '.join(provenance['metric_definition_versions']) or '-'}",
        "",
        "## Runs",
        "",
        "| suite | run | conditions | scored | failed | quality | latency med (ms) | gate |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for run in summary["runs"]:
        lines.append(
            "| {suite} | `{run_id}` | {conditions} | {scored} | {failed} | {quality} | {latency} | {gate} |".format(
                suite=run["suite"],
                run_id=run["run_id"],
                conditions=condition_label(run["conditions"]),
                scored=_format(run["n_scored"], 0),
                failed=_format(run["n_failed"], 0),
                quality=_format(run["quality_mean"]),
                latency=_format(run["latency_median_ms"], 1),
                gate=_format(run["gate_status"]),
            )
        )
    lines += [
        "",
        "## Suite summary",
        "",
        "| suite | runs | scored | mean of run means | distinct means | gates |",
        "|---|---|---|---|---|---|",
    ]
    for suite, stats in summary["by_suite"].items():
        lines.append(
            "| {suite} | {runs} | {scored} | {meanq} | {distinct} | {gates} |".format(
                suite=suite,
                runs=stats["n_runs"],
                scored=stats["n_scored"],
                meanq=_format(stats["quality_mean_of_runs"]),
                distinct=stats["distinct_quality_means"],
                gates=", ".join(f"{name}={count}" for name, count in sorted(stats["gate_statuses"].items())),
            )
        )
    lines += [
        "",
        "## Suite identities (comparability)",
        "",
        "Runs are comparable only when these match within the same suite.",
        "",
        "| suite | dataset hashes | task hashes | metric versions |",
        "|---|---|---|---|",
    ]
    for suite, identity in summary["suite_identities"].items():
        lines.append(
            "| {suite} | {datasets} | {tasks} | {metrics} |".format(
                suite=suite,
                datasets=", ".join(value[:12] for value in identity["dataset_hashes"]) or "-",
                tasks=", ".join(value[:12] for value in identity["task_hashes"]) or "-",
                metrics=", ".join(identity["metric_definition_versions"]) or "-",
            )
        )
    lines += ["", "## Warnings", ""]
    lines += [f"- {warning}" for warning in summary["warnings"]] or ["- none"]
    lines += [
        "",
        "## Re-analyse (no GPU needed)",
        "",
        "```bash",
        "apertus-eval-prep platform-ingest-runs --runs <run dirs> --out comparison_points.json",
        "apertus-eval-prep platform-select --points comparison_points.json \\",
        "  --constraints configs/studies/phase8_sarvam_application_study/selection_constraints.json \\",
        "  --out selection.json",
        "```",
        "",
        "Recompute this file with:",
        "",
        "```bash",
        f"python3 scripts/summarise_real_model_results.py {summary['source_root']}",
        "```",
        "",
    ]
    return "\n".join(lines)


def write_summary(root: Path, *, json_name: str = "summary.json", md_name: str = "summary.md", echo: bool = False) -> dict[str, Any]:
    """Build the summary and write both derived files next to the run tree."""
    summary = build_summary(root)
    json_path = root / json_name
    md_path = root / md_name
    json_path.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(summary), encoding="utf-8")
    if echo:
        print(md_path.read_text(encoding="utf-8"))
    print(f"wrote {json_path} and {md_path}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path, help="Curated result directory holding run subdirectories.")
    parser.add_argument("--json-name", default="summary.json")
    parser.add_argument("--md-name", default="summary.md")
    parser.add_argument("--print", dest="echo", action="store_true", help="Also print the Markdown summary.")
    args = parser.parse_args()
    if not args.root.is_dir():
        parser.error(f"not a directory: {args.root}")
    write_summary(args.root, json_name=args.json_name, md_name=args.md_name, echo=args.echo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


