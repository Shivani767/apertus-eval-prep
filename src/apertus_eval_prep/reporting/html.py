"""Dependency-free, escaped static HTML reports."""
from __future__ import annotations
import json
from typing import Any, Mapping
from apertus_eval_prep.core.evidence import evidence_from_manifest
from apertus_eval_prep.reporting import htmlkit

def _e(v: Any) -> str:
    return htmlkit.escape(v)

def _f(v: Any) -> str:
    """Card/table scalar formatting: explicit when missing, grouped for big numbers."""
    return "Unavailable" if v is None else (htmlkit.number(v) if isinstance(v, float) else str(v))

def _j(v: Any) -> str:
    return _e(json.dumps(v, indent=2, ensure_ascii=False, default=str))

def _rows(headers: list[str], rows: list[list[Any]]) -> str:
    return htmlkit.table(headers, rows)

def _s(title: str, body: str) -> str:
    return htmlkit.section(title, body)

def render_run_html(payload: Mapping[str, Any]) -> str:
    m = payload.get("manifest") or {}; x = payload.get("metrics") or {}
    q = x.get("quality") or {}; fp = payload.get("failure_fingerprint") or {}
    ev = evidence_from_manifest(m)
    mode = str(ev.get("mode") or "UNKNOWN")
    if mode in {"MOCK", "SYNTHETIC"}:
        badge = f"{mode} / SYNTHETIC — NOT REAL BENCHMARK EVIDENCE"
    elif mode == "LOCAL_REAL_MODEL":
        badge = "LOCAL REAL MODEL — EXPERIMENTAL EVIDENCE, NOT PRODUCTION APPROVAL"
    else:
        badge = f"{mode} — EVIDENCE DOES NOT ESTABLISH PRODUCTION VALIDATION"
    model = m.get("model") or {}; backend = m.get("backend") or {}; dataset = m.get("dataset") or {}
    ci = (x.get("confidence_intervals") or {}).get("quality_mean") or {}
    cards = [("Evidence mode", mode), ("Runtime", ev.get("runtime_environment")), ("Hardware measured", ev.get("hardware_measured")), ("Human reviewed", ev.get("human_reviewed")), ("Total", x.get("n_total")), ("Successful", x.get("n_successful")), ("Failed", x.get("n_failed")), ("Skipped", x.get("n_skipped")), ("Mean quality", q.get("mean"))]
    card_html = "".join(f"<div class='card'><b>{_e(k)}</b><strong>{_e(_f(v))}</strong></div>" for k, v in cards)
    p = [f"<div class='cards'>{card_html}</div>"]
    p.append(_s("Provenance and configuration", _rows(["Field", "Value"], [["Run", m.get("run_id")], ["UTC", m.get("utc")], ["Dataset", dataset.get("path")], ["Dataset hash", dataset.get("hash")], ["Task", dataset.get("tasks")], ["Episodes", (x.get("system") or {}).get("episode_count")], ["Model", model.get("model_id")], ["Revision", model.get("model_revision")], ["Backend/device", f"{model.get('adapter_kind')} / {backend.get('device')}"], ["Config hash", m.get("config_hash")], ["Git", (m.get("git") or {}).get("commit")]])))
    p.append(_s("Quality and confidence", _rows(["Metric", "Value", "n"], [["Mean", q.get("mean"), q.get("n_scored")], ["Accuracy", q.get("accuracy"), q.get("n_scored")], ["Std dev", q.get("std"), q.get("n_scored")], ["95% CI", f"{_f(ci.get('lo'))} – {_f(ci.get('hi'))}", ci.get("n")]])))
    if x.get("baseline_comparison"): p.append(_s("Baseline/candidate comparison", f"<pre>{_j(x['baseline_comparison'])}</pre>"))
    for key, title in (("system", "RAG/agent and tool-use metrics"), ("safety", "Safety and risk"), ("deployment", "Cost, latency, and deployment")):
        if x.get(key): p.append(_s(title, _rows(["Metric", "Value"], [[k, v] for k, v in x[key].items()])))
    if x.get("pareto") or x.get("selection"): p.append(_s("Pareto/selection", f"<pre>{_j(x.get('pareto') or x.get('selection'))}</pre>"))
    gate = x.get("release_gate") or {}; reasons = "".join(f"<li>{_e(v)}</li>" for v in gate.get("reasons") or [])
    p.append(_s("Release gate", f"<p><b>Status:</b> {_e(gate.get('status', 'INCONCLUSIVE'))}</p><ul>{reasons}</ul><p>Release-gate results are engineering policy aids and are not production approval.</p>"))
    p.append(_s("Failure fingerprint", _rows(["Metric", "Value"], [["Failures", fp.get("n_failures")], ["Rate", fp.get("failure_rate")], ["Safety-critical", fp.get("safety_critical_failures")], ["Condition-sensitive", len(fp.get("condition_sensitive_failures") or [])], ["Top priority", fp.get("top_investigation_priority")]]) + f"<pre>{_j({'categories': fp.get('by_category', {}), 'severity': fp.get('by_severity', {}), 'baseline': fp.get('baseline_comparison')})}</pre>"))
    examples = fp.get("representative_sanitized_examples") or (payload.get("failures") or [])[:10]
    details = "".join(f"<details><summary>{_e(v.get('failure_id') or v.get('example_id') or v.get('episode_id') or v.get('test_id'))}</summary><pre>{_j(v)}</pre></details>" for v in examples)
    limitations = ev.get("known_limitations") or []
    limitation_items = "".join(f"<li>{_e(item)}</li>" for item in limitations)
    p += [_s("Representative sanitized failures", details or "<p class='note'>Unavailable / no representative failures.</p>"), _s("Missing evidence and limitations", "<p class='note'>Unavailable values are not measured zero. Failure patterns are observations, not causal conclusions. Automated checks are not safety certification.</p><ul>" + limitation_items + "</ul>"), _s("Reproduction", f"<pre>{_e(m.get('entrypoint_command', 'Unavailable'))}</pre>")]
    return htmlkit.page("LLM Evaluation Run Report", "".join(p), badge=badge)

__all__ = ["render_run_html"]
