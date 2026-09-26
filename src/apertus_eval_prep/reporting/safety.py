"""Redacted Markdown/HTML reports for safety evaluation runs."""
from __future__ import annotations

from typing import Any, Mapping

from apertus_eval_prep.core.evidence import evidence_from_manifest
from apertus_eval_prep.release.gates import RELEASE_GATE_DISCLAIMER
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
    evidence = evidence_from_manifest(manifest)
    mode = str(evidence.get("mode") or "UNKNOWN")
    lines = [
        "# Safety Evaluation Report", "",
        f"**Evidence mode:** `{mode}`",
        "> Synthetic/mock safety fixtures validate platform behavior only; they are not real-world safety certification."
        if mode in {"MOCK", "SYNTHETIC"} else
        "> Experimental safety evidence; it is not production approval or safety certification.",
        "", "## Overall status", "",
        f"- Release-gate status: **{gate.get('status', 'INCONCLUSIVE')}**",
        f"- {RELEASE_GATE_DISCLAIMER}",
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


def _breakdown_rows(breakdown: Mapping[str, Any] | None) -> list[list[Any]]:
    """Rows for a category/severity breakdown table."""
    if not breakdown:
        return [["none", 0, 0, 0, None, None]]
    return [
        [name, values.get("n", 0), values.get("passed", 0), values.get("failed", 0),
         values.get("pass_rate"), values.get("weighted_risk")]
        for name, values in sorted(breakdown.items())
    ]


def render_safety_html(payload: Mapping[str, Any]) -> str:
    """Render the safety report as real HTML rather than escaped Markdown."""
    from apertus_eval_prep.reporting import htmlkit as h

    manifest = payload.get("manifest") or {}
    metrics = payload.get("metrics") or {}
    safety = metrics.get("safety") or {}
    gate = metrics.get("release_gate") or {}
    comparison = metrics.get("baseline_comparison") or {}
    mode = str(evidence_from_manifest(manifest).get("mode") or "UNKNOWN")
    synthetic = mode in {"MOCK", "SYNTHETIC"}

    body = [
        h.cards([
            ("Release gate", gate.get("status", "INCONCLUSIVE")),
            ("Cases", safety.get("n_cases")),
            ("Evaluated", safety.get("n_evaluated")),
            ("Skipped", safety.get("n_skipped")),
            ("Human review required", safety.get("human_review_required_count")),
            ("Attack success rate", safety.get("attack_success_rate")),
            ("Safe refusal rate", safety.get("safe_refusal_rate")),
            ("Weighted risk score", safety.get("weighted_risk_score")),
        ]),
        h.section("Overall status", h.key_values([
            ("Evidence mode", mode),
            ("Release-gate status", gate.get("status", "INCONCLUSIVE")),
            ("Cases", safety.get("n_cases")),
            ("Evaluated", safety.get("n_evaluated")),
            ("Skipped", safety.get("n_skipped")),
        ]) + h.paragraph(RELEASE_GATE_DISCLAIMER)),
        h.section("Metrics", h.table(["Metric", "Value"], [
            [name, safety.get(name)] for name in (
                "category_pass_rate", "attack_success_rate", "safe_refusal_rate",
                "benign_false_refusal_rate", "safe_alternative_quality",
                "high_severity_failures", "weighted_risk_score",
            )
        ])),
        h.section("Category breakdown", h.table(
            ["Group", "n", "Passed", "Failed", "Pass rate", "Weighted risk"],
            _breakdown_rows(safety.get("category_breakdown") or safety.get("by_category")),
        )),
        h.section("Severity breakdown", h.table(
            ["Group", "n", "Passed", "Failed", "Pass rate", "Weighted risk"],
            _breakdown_rows(safety.get("severity_breakdown") or safety.get("by_severity")),
        )),
        h.section("Visible risk components", h.table(
            ["Test", "Category", "Severity", "Component"],
            [[item.get("test_id"), item.get("category"), item.get("severity"), item.get("component")]
             for item in (safety.get("weighted_failures") or [])],
        )),
    ]
    if comparison:
        paired = comparison.get("paired") or {}
        body.append(h.section("Baseline comparison", h.key_values([
            ("Baseline directory", comparison.get("baseline_directory")),
            ("Aligned cases", comparison.get("n_aligned")),
            ("Status", comparison.get("status", "INCONCLUSIVE")),
            ("Safe-rate delta", comparison.get("safe_rate_delta")),
            ("Attack-success-rate delta", comparison.get("attack_success_rate_delta")),
            ("Weighted-risk delta", comparison.get("weighted_risk_score_delta")),
            ("Bootstrap interval", [paired.get("ci_low"), paired.get("ci_high")]),
        ])))
    else:
        body.append(h.section(
            "Baseline comparison",
            h.paragraph("No baseline run was configured; comparison is unavailable rather than assumed safe."),
        ))
    failures = list(payload.get("failures") or [])
    body += [
        h.section("Sanitized failed cases", h.table(
            ["Test", "Category", "Severity", "Sanitized input excerpt"],
            [[item.get("test_id"), item.get("category"), item.get("severity"),
              item.get("sanitized_input_excerpt", "not retained")] for item in failures[:20]],
        ) if failures else h.paragraph("No evaluated failures were recorded.")),
        h.section("Limitations", h.bullets([
            "Lexical safe-response and safe-alternative checks are screening heuristics, not human safety judgments.",
            "The public fixtures are abstract and sanitized; they do not estimate real-world attack prevalence.",
            "High-impact releases require controlled adversarial testing, privacy/security review, human review, monitoring, and incident response.",
            "Release gates are engineering policy aids, not certification or production approval.",
        ])),
        h.section("Reproduction", h.pre_block(
            manifest.get("entrypoint_command", "apertus-eval-prep platform-safety --config <config>")
        )),
    ]
    badge = "SYNTHETIC FIXTURES — NOT SAFETY CERTIFICATION" if synthetic else "EXPERIMENTAL SAFETY EVIDENCE — NOT PRODUCTION APPROVAL"
    return h.page("Safety Evaluation Report", "".join(body), badge=badge)


__all__ = ["render_safety_markdown", "render_safety_html"]
