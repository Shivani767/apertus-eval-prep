"""Static experiment-matrix reports."""
from __future__ import annotations

import html
from typing import Any, Mapping


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _ci(interval: Any) -> str:
    if not isinstance(interval, Mapping):
        return "—"
    return f"[{_fmt(interval.get('lo'))}, {_fmt(interval.get('hi'))}]"


def render_experiment_markdown(result: Mapping[str, Any]) -> str:
    report = result.get("report") or {}
    summary = report.get("experiment_summary") or {}
    comparison = report.get("baseline_vs_first_candidate") or {}
    quality = report.get("quality_summary") or {}
    factors = ((report.get("factor_metrics") or {}).get("factors") or [])
    intervals = report.get("confidence_intervals") or {}
    rcs = report.get("robust_capability_score") or {}
    lines = [
        "# Experiment matrix report", "",
        f"- Experiment: `{result.get('experiment_id')}`",
        f"- Parent experiment: `{report.get('parent_experiment_id', result.get('experiment_id'))}`",
        f"- Cells: `{summary.get('n_ok', 0)}` successful / `{summary.get('n_cells', 0)}` planned",
        f"- Evaluated examples across cells: `{summary.get('n_examples', 0)}`",
        f"- Errors: `{summary.get('n_error', 0)}`", "",
        "## Baseline/candidate conclusion", "",
        f"- Baseline cell: `{report.get('baseline_cell')}`",
        f"- Candidate cell: `{report.get('candidate_cell')}`",
        f"- Status: **{comparison.get('status', 'INCONCLUSIVE')}**",
        f"- Delta (candidate - baseline): `{_fmt(comparison.get('delta'))}`",
        f"- 95% bootstrap CI: `{_ci({'lo': comparison.get('ci_low'), 'hi': comparison.get('ci_high')})}`",
        f"- Aligned examples: `{comparison.get('n_paired', 0)}`",
        f"- Effect size: `{_fmt(comparison.get('effect_size'))}` ({comparison.get('effect_size_name', 'paired effect')})", "",
        "## Quality summary", "",
        f"- Count: `{quality.get('count', 0)}`",
        f"- Mean quality: `{_fmt(quality.get('mean'))}`",
        f"- Standard deviation: `{_fmt(quality.get('std'))}`",
        f"- Standard error: `{_fmt(quality.get('standard_error'))}`",
        f"- 95% CI: `{_ci(quality.get('confidence_interval'))}`", "",
        "## Factor breakdown", "",
        "| Factor | Level | Mean | n | 95% CI | Unstable |",
        "|---|---|---:|---:|---|---|",
    ]
    for factor in factors:
        for level, summary_row in (factor.get("levels") or {}).items():
            lines.append(
                f"| `{factor.get('factor')}` | `{level}` | {_fmt(summary_row.get('mean'))} | "
                f"{summary_row.get('n_scored', 0)} | {_ci(summary_row.get('confidence_interval'))} | "
                f"{summary_row.get('mean') is not None and factor.get('unstable', False)} |"
            )
    lines += [
        "", "## Confidence intervals", "",
        f"- Across-cell mean CI: `{_ci(intervals.get('cell_quality_mean'))}`",
        "", "## Experimental Robust Capability Score", "",
        f"- Mean quality: `{_fmt(rcs.get('mean_quality'))}`",
        f"- Configuration variance: `{_fmt(rcs.get('configuration_variance'))}`",
        f"- Lambda: `{_fmt(rcs.get('lambda'))}`",
        f"- RCS: `{_fmt(rcs.get('score'))}`",
        f"- Experimental: `{rcs.get('experimental', True)}`", "",
        "## Unstable conditions", "",
    ]
    unstable = report.get("unstable_conditions") or []
    lines.extend([f"- `{factor}`" for factor in unstable] or ["- None identified."])
    lines += ["", "## Representative sensitive failures", ""]
    sensitive = report.get("representative_sensitive_failures") or []
    if sensitive:
        lines.extend([
            f"- `{item.get('example_id')}`: {', '.join(item.get('classifications') or [item.get('classification', 'condition_sensitive')])}"
            for item in sensitive
        ])
    else:
        lines.append("- None identified.")
    lines += [
        "", "## Reproduction", "", f"`{report.get('reproduction_command', '<command>')}`", "",
        "## Limitations", "",
        *[f"- {limitation}" for limitation in report.get("limitations", [])],
        "- Synthetic/mock cells validate platform behavior only; they are not real model benchmark results.",
    ]
    return "\n".join(lines) + "\n"


def render_experiment_html(result: Mapping[str, Any]) -> str:
    text = render_experiment_markdown(result)
    return "<!doctype html><html><head><meta charset='utf-8'><title>Experiment matrix</title></head><body><pre>" + html.escape(text) + "</pre></body></html>\n"


__all__ = ["render_experiment_markdown", "render_experiment_html"]
