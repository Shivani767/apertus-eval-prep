"""Redacted Markdown/HTML reports for safety evaluation runs."""
from __future__ import annotations

import html
from typing import Any, Mapping

from apertus_eval_prep.utils.pii import redact_text_for_report


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _text(value: Any) -> str:
    return redact_text_for_report(str(value if value is not None else ""))


def _breakdown(title: str, breakdown: Mapping[str, Any] | None) -> list[str]:
    lines = [f"## {title}", "", "| Group | n | Passed | Failed | Pass rate | Weighted risk |", "|---|---:|---:|---:|---:|---:|"]
    for name, values in sorted((breakdown or {}).items()):
        lines.append(
            f"| `{_text(name)}` | {values.get('n', 0)} | {values.get('passed', 0)} | "
            f"{values.get('failed', 0)} | {_fmt(values.get('pass_rate'))} | {_fmt(values.get('weighted_risk'))} |"
        )
    if not breakdown:
        lines.append("| _none_ | 0 | 0 | 0 | — | — |")
    return lines


def render_safety_markdown(payload: Mapping[str, Any]) -> str:
    manifest = payload.get("manifest") or {}
    metrics = payload.get("metrics") or {}
    safety = metrics.get("safety") or {}
    gate = metrics.get("release_gate") or {}
    comparison = metrics.get("baseline_comparison") or {}
    evidence = str(manifest.get("evidence_class") or metrics.get("evidence_class") or "MEASURED")
    lines = [
        "# Safety Evaluation Report", "",
        f"**Evidence class:** `{evidence}`",
        "> Synthetic/mock safety fixtures validate platform behavior only; they are not real-world safety certification.",
        "", "## Overall status", "",
        f"- Release-gate status: **{gate.get('status', 'INCONCLUSIVE')}**",
        f"- Cases: `{safety.get('n_cases', 0)}` total / `{safety.get('n_evaluated', 0)}` evaluated / `{safety.get('n_skipped', 0)}` skipped",
        f"- Human review required: `{safety.get('human_review_required_count', 0)}` cases", "",
        "## Metrics", "", "| Metric | Value |", "|---|---:|",
    ]
    for name in (
        "category_pass_rate", "attack_success_rate", "safe_refusal_rate",
        "benign_false_refusal_rate", "safe_alternative_quality",
        "high_severity_failures", "weighted_risk_score",
    ):
        lines.append(f"| {name} | {_fmt(safety.get(name))} |")
    lines += _breakdown("Category breakdown", safety.get("category_breakdown") or safety.get("by_category"))
    lines += _breakdown("Severity breakdown", safety.get("severity_breakdown") or safety.get("by_severity"))
    lines += ["", "## Visible risk components", "", "| Test | Category | Severity | Component |", "|---|---|---|---:|"]
    for item in safety.get("weighted_failures") or []:
        lines.append(f"| `{_text(item.get('test_id'))}` | `{_text(item.get('category'))}` | `{_text(item.get('severity'))}` | {_fmt(item.get('component'))} |")
    if not safety.get("weighted_failures"):
        lines.append("| _none_ | — | — | — |")
    lines += ["", "## Baseline comparison", ""]
    if comparison:
        paired = comparison.get("paired") or {}
        lines += [
            f"- Baseline directory: `{_text(comparison.get('baseline_directory'))}`",
            f"- Aligned cases: `{comparison.get('n_aligned', 0)}`",
            f"- Status: **{comparison.get('status', 'INCONCLUSIVE')}**",
            f"- Safe-rate delta: `{_fmt(comparison.get('safe_rate_delta'))}`",
            f"- Attack-success-rate delta: `{_fmt(comparison.get('attack_success_rate_delta'))}`",
            f"- Weighted-risk delta: `{_fmt(comparison.get('weighted_risk_score_delta'))}`",
            f"- Bootstrap interval: `[{_fmt(paired.get('ci_low'))}, {_fmt(paired.get('ci_high'))}]`",
        ]
    else:
        lines.append("No baseline run was configured; comparison is unavailable rather than assumed safe.")
    lines += ["", "## Sanitized failed cases", ""]
    failures = list(payload.get("failures") or [])
    if failures:
        lines += ["| Test | Category | Severity | Sanitized input excerpt |", "|---|---|---|---|"]
        for item in failures[:20]:
            lines.append(f"| `{_text(item.get('test_id'))}` | `{_text(item.get('category'))}` | `{_text(item.get('severity'))}` | {_text(item.get('sanitized_input_excerpt', 'not retained'))} |")
    else:
        lines.append("No evaluated failures were recorded.")
    lines += [
        "", "## Limitations", "",
        "- Lexical safe-response and safe-alternative checks are screening heuristics, not human safety judgments.",
        "- The public fixtures are abstract and sanitized; they do not estimate real-world attack prevalence.",
        "- High-impact releases require controlled adversarial testing, privacy/security review, human review, monitoring, and incident response.",
        "- Release gates are engineering policy aids, not certification or production approval.",
        "", "## Reproduction", "",
        f"`{_text(manifest.get('entrypoint_command', 'apertus-eval-prep platform-safety --config <config>'))}`",
    ]
    return "\n".join(lines) + "\n"


def render_safety_html(payload: Mapping[str, Any]) -> str:
    text = render_safety_markdown(payload)
    return "<!doctype html><html><head><meta charset='utf-8'><title>Safety Evaluation Report</title></head><body><pre>" + html.escape(text) + "</pre></body></html>\n"


__all__ = ["render_safety_markdown", "render_safety_html"]
