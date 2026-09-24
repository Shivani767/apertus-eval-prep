"""Dependency-free Markdown reporting for platform runs."""
from __future__ import annotations

import json
from typing import Any, Mapping

from apertus_eval_prep.utils.pii import redact_text_for_report


def _safe(value: Any) -> str:
    text = redact_text_for_report(str(value if value is not None else ""))
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _section(title: str, rows: list[tuple[str, Any]]) -> list[str]:
    lines = [f"## {title}", "", "| metric | value |", "|---|---|"]
    lines.extend(f"| {_safe(name)} | {_metric(value)} |" for name, value in rows)
    lines.append("")
    return lines


def _safe_json(value: Any) -> str:
    return _safe(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def _count(value: Any) -> Any:
    return "unavailable" if value is None else value


def _metric(value: Any) -> str:
    """Preserve measured numeric formatting; redact/escape textual values."""
    if value is None or isinstance(value, (int, float, bool)):
        return _fmt(value)
    return _safe(value)


def _ci_text(value: Any) -> str:
    return "unavailable" if value is None else value


def render_run_markdown(payload: Mapping[str, Any]) -> str:
    manifest = payload.get("manifest") or {}
    metrics = payload.get("metrics") or {}
    fingerprint = payload.get("failure_fingerprint") or {}
    quality = metrics.get("quality") or {}
    model = manifest.get("model") or {}
    backend = manifest.get("backend") or {}
    evidence = str(manifest.get("evidence_class") or metrics.get("evidence_class") or "MEASURED")
    synthetic = evidence in {"MOCK", "DEMO", "DEMONSTRATION"}
    lines = [
        "# LLM Evaluation Run Report", "",
        f"**Evidence class:** `{evidence}`" + ("  \\n> Synthetic/mock evidence; not a real benchmark result." if synthetic else ""),
        "", "## Run identity", "",
        f"- Run ID: `{manifest.get('run_id', 'unknown')}`",
        f"- UTC: `{manifest.get('utc', 'unknown')}`",
        f"- Model: `{_safe(model.get('model_id', 'unknown'))}` (revision `{_safe(model.get('model_revision') or 'unspecified')}`)",
        f"- Adapter/backend: `{_safe(model.get('adapter_kind', 'unknown'))}` / `{_safe(backend.get('device', 'unknown'))}`",
        f"- Config hash: `{manifest.get('config_hash', 'unknown')}`",
        f"- Git commit: `{_safe(((manifest.get('git') or {}).get('commit') or 'unavailable'))}`",
        "", "## Dataset, task, and episode context", "",
        f"- Dataset: `{_safe((manifest.get('dataset') or {}).get('path') or 'unavailable')}` (hash `{_safe((manifest.get('dataset') or {}).get('hash') or 'unavailable')}`)",
        f"- Task: `{_safe((manifest.get('dataset') or {}).get('tasks') or 'unavailable')}`",
        f"- Episodes: `{_safe((metrics.get('system') or {}).get('episode_count'))}`",
        "", "## Coverage and quality", "",
        "| metric | value | n |", "|---|---:|---:|",
        f"| Mean quality | {_fmt(quality.get('mean'))} | {quality.get('n_scored', 0)} |",
        f"| Accuracy | {_fmt(quality.get('accuracy'))} | {quality.get('n_scored', 0)} |",
        f"| Standard deviation | {_fmt(quality.get('std'))} | {quality.get('n_scored', 0)} |",
        f"| p95 latency (ms) | {_fmt((metrics.get('latency') or {}).get('p95_ms'))} | {(metrics.get('latency') or {}).get('n_total', 0)} |",
        f"| Failed examples | {metrics.get('n_failed', 0)} | {metrics.get('n_total', 0)} |",
        "", "## Uncertainty", "",
    ]
    ci = (metrics.get("confidence_intervals") or {}).get("quality_mean") or {}
    lines.append(f"Bootstrap 95% interval for the mean: `{_fmt(ci.get('lo'))}` to `{_fmt(ci.get('hi'))}` (n={ci.get('n', 0)}).")
    lines += ["", "## Release decision", "", f"- Status: **{((metrics.get('release_gate') or {}).get('status', 'INCONCLUSIVE'))}**", ""]
    reasons = (metrics.get("release_gate") or {}).get("reasons") or []
    lines += [f"- {_safe(reason)}" for reason in reasons] or ["- No release-gate reasons were recorded."]
    failures = list(payload.get("failures") or [])
    lines += _section("Failure fingerprint", [
        ("Recorded failures", fingerprint.get("n_failures", len(failures))),
        ("Failure rate", fingerprint.get("failure_rate")),
        ("Safety-critical failures", fingerprint.get("safety_critical_failures", 0)),
        ("Stable failures", len(fingerprint.get("stable_failures") or [])),
        ("Condition-sensitive failures", len(fingerprint.get("condition_sensitive_failures") or [])),
        ("Investigation priority", fingerprint.get("top_investigation_priority")),
    ])
    lines += ["", "### Failure categories", "", "| category | count |", "|---|---:|"]
    for category, count in sorted((fingerprint.get("by_category") or {}).items()):
        lines.append(f"| `{_safe(category)}` | {count} |")
    lines += ["", "### Representative sanitized failure examples", ""]
    representatives = fingerprint.get("representative_sanitized_examples") or []
    if representatives:
        for item in representatives[:10]:
            identity = item.get("example_id") or item.get("episode_id") or item.get("test_id") or item.get("failure_id")
            lines.append(f"- `{_safe(identity)}` — `{_safe(item.get('failure_type') or item.get('category'))}` ({_safe(item.get('severity'))}): {_safe(item.get('sanitized_input_excerpt') or 'input not retained')}")
    else:
        lines.append("No representative failures were recorded; this is not evidence that no failures exist.")
    if fingerprint.get("baseline_comparison", {}).get("status") == "OBSERVED_DELTA":
        lines += ["", "### Baseline/candidate failure delta", "", "```json", _safe_json(fingerprint["baseline_comparison"]), "```"]
    lines += ["", "## Coverage and missing evidence", "",
              f"- Total records: `{_count(metrics.get('n_total'))}`",
              f"- Successful records: `{_count(metrics.get('n_successful'))}`",
              f"- Failed records: `{_count(metrics.get('n_failed'))}`",
              f"- Skipped/unavailable records: `{_count(metrics.get('n_skipped'))}`",
              "- Missing evidence is shown as `—` or `unavailable`, never as a measured zero.", ""]
    if metrics.get("baseline_comparison"):
        lines += ["", "## Baseline/candidate comparison", "", "```json", _safe_json(metrics["baseline_comparison"]), "```"]
    if metrics.get("pareto") or metrics.get("selection"):
        lines += ["", "## Pareto/selection context", "", "```json", _safe_json(metrics.get("pareto") or metrics.get("selection")), "```"]
    system = metrics.get("system") or {}
    if system:
        lines += ["", "## RAG/agent metrics", "", "| metric | value |", "|---|---:|"]
        for key in ("episode_count", "task_completion_rate", "groundedness_mean", "tool_schema_validity", "tool_sequence_validity", "tool_call_efficiency", "tool_call_count", "unnecessary_tool_call_count", "recovery_success_rate", "step_count_mean", "end_to_end_latency_ms_mean", "unsupported_claim_rate", "source_citation_coverage", "unsafe_action_count", "input_tokens", "output_tokens", "token_count", "usage_reported"):
            lines.append(f"| {key} | {_metric(system.get(key))} |")
    safety = metrics.get("safety") or {}
    if safety:
        lines += ["", "## Safety metrics", "", "| metric | value |", "|---|---:|"]
        for key in ("category_pass_rate", "attack_success_rate", "safe_refusal_rate", "benign_false_refusal_rate", "high_severity_failures", "weighted_risk_score"):
            lines.append(f"| {key} | {_metric(safety.get(key))} |")
    deployment = metrics.get("deployment") or {}
    if deployment:
        lines += ["", "## Deployment trade-offs", "", "| metric | value |", "|---|---:|"]
        for key in ("latency_mean_ms", "latency_p50_ms", "latency_p95_ms", "throughput", "input_tokens", "output_tokens", "cost_per_success", "run_failures"):
            lines.append(f"| {key} | {_metric(deployment.get(key))} |")
        if deployment.get("cost", {}).get("quality") == "UNAVAILABLE":
            lines.append("\nCost is unavailable rather than zero; configure prices explicitly.")
    rcs = metrics.get("robust_capability_score")
    if rcs:
        lines += ["", "## Robust Capability Score (experimental)", "",
                  f"- Mean quality: `{_fmt(rcs.get('mean_quality'))}`",
                  f"- Configuration variance: `{_fmt(rcs.get('configuration_variance'))}`",
                  f"- Lambda: `{_fmt(rcs.get('lambda'))}`", f"- RCS: `{_fmt(rcs.get('score'))}`", ""]
    lines += [
        "", "## Limitations", "",
        "- This report distinguishes observed measurements from synthetic/mock evidence; it does not certify a model or deployment.",
        "- Rule-based quality, groundedness, and uncertainty summaries do not replace human review for high-impact use cases.",
        "- Raw retention and PII redaction are controlled by the resolved run configuration.",
        "", "## Reproduction", "",
        f"`{_safe(manifest.get('entrypoint_command', 'apertus-eval-prep platform-run --config <config>'))}`",
    ]
    return "\n".join(lines) + "\n"


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


__all__ = ["render_run_markdown"]
