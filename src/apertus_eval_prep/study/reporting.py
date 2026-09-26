"""Static study reports and artifact bundle writers."""
from __future__ import annotations
import csv
import html
from pathlib import Path
from typing import Any, Mapping
from apertus_eval_prep.utils.pii import redact_text_for_report
from apertus_eval_prep.utils.serialization import write_json, write_text


def _e(value: Any) -> str:
    return html.escape(redact_text_for_report(str(value if value is not None else "")), quote=True)


def _f(value: Any) -> str:
    if value is None:
        return "unavailable"
    return f"{value:.4f}" if isinstance(value, float) else str(value)


def _md(value: Any) -> str:
    text = redact_text_for_report(str(value if value is not None else ""))
    return text.replace("\\", "\\\\").replace("`", "\\`").replace("|", "\\|").replace("\n", " ")


def _ci(interval: Any) -> str:
    if not isinstance(interval, Mapping):
        return "unavailable"
    return f"[{_f(interval.get('lo'))}, {_f(interval.get('hi'))}]"


def render_study_markdown(summary: Mapping[str, Any]) -> str:
    study = summary.get("study") or {}
    modes = summary.get("evidence_modes") or []
    real = bool(summary.get("real_model_evidence_available"))
    notice = "Experimental real-model evidence; not production approval." if real else "No real-model evidence available; synthetic/framework validation only."
    rows = list(summary.get("rows") or [])
    lines = [
        "# Phase 8 Experimental Study Report", "",
        f"- Study: `{_md(study.get('study_id'))}`",
        f"- Title: {_md(study.get('study_title') or 'unavailable')}",
        f"- Evidence: `{_md(', '.join(modes) or 'unavailable')}`",
        f"> {notice}", "",
        "## Study design and provenance", "",
        f"- Research question: {_md(study.get('research_question') or 'unavailable')}",
        f"- Hypotheses: `{_md(', '.join(study.get('hypothesis_ids') or []) or 'unavailable')}`",
        f"- Planned samples: `{_md(study.get('planned_sample_counts') or 'unavailable')}`",
        f"- Protocol: `{_md(study.get('protocol_path') or 'unavailable')}`",
        f"- Preregistration: `{_md(study.get('preregistration_path') or 'unavailable')}`",
        f"- Deviations: `{_md((summary.get('deviations') or {}).get('status', 'NOT_ASSESSED'))}`", "",
        "## Model/configuration summary", "",
        "| Run | Model/revision | Evidence | Config hash | Quality | 95% CI |",
        "|---|---|---|---|---:|---|",
    ]
    for row in rows:
        quality = row.get("quality") or {}; ci = (row.get("confidence_intervals") or {}).get("quality_mean")
        lines.append(f"| `{_md(row.get('run_id'))}` | `{_md(row.get('model_id'))}` / `{_md(row.get('model_revision'))}` | `{_md(row.get('evidence_mode'))}` | `{_md(row.get('config_hash'))}` | {_f(quality.get('mean'))} | {_ci(ci)} |")
    lines += ["", "## Comparisons", ""]
    for comparison in summary.get("comparisons") or []:
        lines.append(
            f"- `{_md(comparison.get('baseline_run'))}` → `{_md(comparison.get('candidate_run'))}`: "
            f"delta `{_f(comparison.get('quality_delta'))}`, 95% CI `[{_f(comparison.get('ci_low'))}, {_f(comparison.get('ci_high'))}]`, "
            f"effect `{_f(comparison.get('effect_size'))}`, status **{_md(comparison.get('status'))}**, "
            f"practically meaningful: `{comparison.get('practically_meaningful', False)}`."
        )
    rcs = summary.get("robust_capability_score") or {}
    lines += ["", "## Experimental Robust Capability Score", "",
              f"- Mean quality: `{_f(rcs.get('mean_quality'))}`",
              f"- Configuration variance: `{_f(rcs.get('configuration_variance'))}`",
              f"- Lambda: `{_f(rcs.get('lambda'))}`", f"- RCS: `{_f(rcs.get('score'))}`",
              f"- Experimental: `{bool(rcs.get('experimental', True))}`", "",
              "## Safety, RAG/agent, and deployment", ""]
    for row in rows:
        safety = row.get("safety") or {}; system = row.get("system") or {}; dep = row.get("deployment") or {}; gate = row.get("release_gate") or {}
        lines.append(
            f"- `{_md(row.get('run_id'))}`: attack success `{_f(safety.get('attack_success_rate'))}`, "
            f"groundedness `{_f(system.get('groundedness_mean'))}`, agent success `{_f(system.get('task_completion_rate'))}`, "
            f"latency p95 `{_f(dep.get('latency_p95_ms'))}`, cost/success `{_f(dep.get('cost_per_success'))}`, "
            f"gate `{_md(gate.get('status', 'INCONCLUSIVE'))}`."
        )
    lines += ["", "## Pareto frontier", ""]
    pareto = (summary.get("pareto") or {}).get("pareto") or {}
    lines += [f"- Pareto-optimal: `{len(pareto.get('frontier', []))}`",
              f"- Dominated: `{len(pareto.get('dominated', []))}`",
              f"- Excluded/inconclusive: `{len(pareto.get('excluded', []))}`"]
    lines += ["", "## Failure fingerprints", ""]
    for row in rows:
        fingerprint = row.get("failure_fingerprint") or {}
        lines.append(f"- `{_md(row.get('run_id'))}`: failures `{_f(fingerprint.get('n_failures'))}`, rate `{_f(fingerprint.get('failure_rate'))}`, priority `{_md(fingerprint.get('top_investigation_priority') or 'unavailable')}`.")
    review = summary.get("review") or {}
    lines += ["", "## Human review", "", f"- Status: `{_e(review.get('status'))}`", f"- Human reviewed: `{bool(review.get('human_reviewed'))}`"]
    lines += ["", "## Missing evidence / inconclusive results", ""]
    unavailable = []
    for row in rows:
        if not row.get("safety"):
            unavailable.append(f"{row.get('run_id')}: safety suite unavailable")
        if not row.get("system"):
            unavailable.append(f"{row.get('run_id')}: RAG/agent suite unavailable")
        if (row.get("deployment") or {}).get("cost_per_success") is None:
            unavailable.append(f"{row.get('run_id')}: cost per successful task unavailable")
    lines.extend([f"- {_md(item)}" for item in unavailable] or ["- None identified."])
    lines += ["", "## Limitations", ""]
    lines.extend(f"- {_md(item)}" for item in summary.get("limitations") or [])
    lines += ["", "## Reproducibility", "", "Underlying run IDs, config hashes, dataset hashes, prompt hashes, and artifact paths are preserved in `study_summary.json` and `comparison_table.csv`."]
    return "\n".join(lines) + "\n"


def render_study_html(summary: Mapping[str, Any]) -> str:
    """Render the study report as real HTML rather than escaped Markdown."""
    from apertus_eval_prep.reporting import htmlkit as h

    study = summary.get("study") or {}
    rows = list(summary.get("rows") or [])
    rcs = summary.get("robust_capability_score") or {}
    review = summary.get("review") or {}
    pareto = (summary.get("pareto") or {}).get("pareto") or {}

    unavailable: list[str] = []
    for row in rows:
        if not row.get("safety"):
            unavailable.append(f"{row.get('run_id')}: safety suite unavailable")
        if not row.get("system"):
            unavailable.append(f"{row.get('run_id')}: RAG/agent suite unavailable")
        if (row.get("deployment") or {}).get("cost_per_success") is None:
            unavailable.append(f"{row.get('run_id')}: cost per successful task unavailable")

    body = [
        h.cards([
            ("Runs", len(rows)),
            ("Evidence modes", ", ".join(summary.get("evidence_modes") or []) or None),
            ("Real-model evidence", bool(summary.get("real_model_evidence_available"))),
            ("Deviations", (summary.get("deviations") or {}).get("status", "NOT_ASSESSED")),
            ("RCS (experimental)", rcs.get("score")),
        ]),
        h.section("Study design and provenance", h.key_values([
            ("Study", study.get("study_id")),
            ("Title", study.get("study_title")),
            ("Research question", study.get("research_question")),
            ("Hypotheses", ", ".join(study.get("hypothesis_ids") or []) or None),
            ("Planned samples", study.get("planned_sample_counts")),
            ("Protocol", study.get("protocol_path")),
            ("Preregistration", study.get("preregistration_path")),
        ])),
        h.section("Runs and configurations", h.table(
            ["Run", "Model", "Revision", "Evidence", "Config hash", "Quality", "95% CI"],
            [
                [
                    row.get("run_id"),
                    row.get("model_id"),
                    row.get("model_revision"),
                    row.get("evidence_mode"),
                    row.get("config_hash"),
                    (row.get("quality") or {}).get("mean"),
                    _ci((row.get("confidence_intervals") or {}).get("quality_mean")),
                ]
                for row in rows
            ],
        )),
        h.section("Comparisons", h.table(
            ["Baseline run", "Candidate run", "Delta", "95% CI", "Effect size", "Status", "Practically meaningful"],
            [
                [
                    comparison.get("baseline_run"),
                    comparison.get("candidate_run"),
                    comparison.get("quality_delta"),
                    _ci({"lo": comparison.get("ci_low"), "hi": comparison.get("ci_high")}),
                    comparison.get("effect_size"),
                    comparison.get("status"),
                    bool(comparison.get("practically_meaningful")),
                ]
                for comparison in (summary.get("comparisons") or [])
            ],
        )),
        h.section("Experimental robust capability score", h.key_values([
            ("Mean quality", rcs.get("mean_quality")),
            ("Configuration variance", rcs.get("configuration_variance")),
            ("Lambda", rcs.get("lambda")),
            ("RCS", rcs.get("score")),
            ("Experimental score", bool(rcs.get("experimental", True))),
        ])),
        h.section("Safety, RAG/agent and deployment", h.table(
            ["Run", "Attack success", "Groundedness", "Agent success", "Latency p95 (ms)", "Cost/success", "Gate"],
            [
                [
                    row.get("run_id"),
                    (row.get("safety") or {}).get("attack_success_rate"),
                    (row.get("system") or {}).get("groundedness_mean"),
                    (row.get("system") or {}).get("task_completion_rate"),
                    (row.get("deployment") or {}).get("latency_p95_ms"),
                    (row.get("deployment") or {}).get("cost_per_success"),
                    (row.get("release_gate") or {}).get("status", "INCONCLUSIVE"),
                ]
                for row in rows
            ],
        )),
        h.section("Failure fingerprints", h.table(
            ["Run", "Failures", "Rate", "Top priority"],
            [
                [
                    row.get("run_id"),
                    (row.get("failure_fingerprint") or {}).get("n_failures"),
                    (row.get("failure_fingerprint") or {}).get("failure_rate"),
                    (row.get("failure_fingerprint") or {}).get("top_investigation_priority"),
                ]
                for row in rows
            ],
        )),
        h.section("Pareto frontier", h.key_values([
            ("Pareto-optimal", len(pareto.get("frontier", []))),
            ("Dominated", len(pareto.get("dominated", []))),
            ("Excluded or inconclusive", len(pareto.get("excluded", []))),
        ])),
        h.section("Human review", h.key_values([
            ("Status", review.get("status", "NOT_PROVIDED")),
            ("Human reviewed", bool(review.get("human_reviewed"))),
            ("Annotations", review.get("n_annotations")),
        ])),
        h.section("Missing evidence and inconclusive results", h.bullets(unavailable)),
        h.section("Limitations", h.bullets(summary.get("limitations") or [])),
        h.section("Reproducibility", h.paragraph(
            "Underlying run IDs, config hashes, dataset hashes, prompt hashes and artifact paths are "
            "preserved in study_summary.json and comparison_table.csv."
        )),
    ]
    return h.page("Phase 8 study report", "".join(body))


def _csv_safe(value: Any) -> Any:
    if isinstance(value, str):
        value = redact_text_for_report(value)
        if value.startswith(("=", "+", "-", "@")):
            return "'" + value
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_rows = [{field: _csv_safe(row.get(field)) for field in fields} for row in rows]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(safe_rows)


def write_study_outputs(summary: Mapping[str, Any], out_dir: str | Path) -> dict[str, str]:
    out = Path(out_dir)
    write_json(out / "study_manifest.json", summary.get("manifest") or {})
    write_json(out / "study_summary.json", summary)
    write_text(out / "study_report.md", render_study_markdown(summary))
    write_text(out / "study_report.html", render_study_html(summary))
    rows = list(summary.get("rows") or [])
    _write_csv(out / "comparison_table.csv", [{"run_id": r.get("run_id"), "model_id": r.get("model_id"), "evidence_mode": r.get("evidence_mode"), "quality": (r.get("quality") or {}).get("mean"), "latency_p95_ms": (r.get("deployment") or {}).get("latency_p95_ms"), "cost_per_success": (r.get("deployment") or {}).get("cost_per_success")} for r in rows], ["run_id", "model_id", "evidence_mode", "quality", "latency_p95_ms", "cost_per_success"])
    _write_csv(out / "metric_summary.csv", [{"run_id": r.get("run_id"), "quality": (r.get("quality") or {}).get("mean"), "groundedness": (r.get("system") or {}).get("groundedness_mean"), "attack_success_rate": (r.get("safety") or {}).get("attack_success_rate"), "variance": (r.get("quality") or {}).get("variance")} for r in rows], ["run_id", "quality", "groundedness", "attack_success_rate", "variance"])
    _write_csv(out / "failure_summary.csv", [{"run_id": r.get("run_id"), "failure_count": (r.get("failure_fingerprint") or {}).get("n_failures"), "failure_rate": (r.get("failure_fingerprint") or {}).get("failure_rate"), "top_priority": (r.get("failure_fingerprint") or {}).get("top_investigation_priority")} for r in rows], ["run_id", "failure_count", "failure_rate", "top_priority"])
    write_json(out / "review_summary.json", summary.get("review") or {})
    write_text(out / "study_limitations.md", "# Study limitations\n\n" + "\n".join(f"- {_md(x)}" for x in summary.get("limitations") or []) + "\n")
    return {"manifest": str(out / "study_manifest.json"), "summary": str(out / "study_summary.json"), "markdown": str(out / "study_report.md"), "html": str(out / "study_report.html")}


__all__ = ["render_study_markdown", "render_study_html", "write_study_outputs"]
