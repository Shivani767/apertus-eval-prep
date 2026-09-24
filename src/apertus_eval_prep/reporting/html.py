"""Dependency-free, escaped static HTML reports."""
from __future__ import annotations
import html
import json
from typing import Any, Mapping
from apertus_eval_prep.utils.pii import redact_text_for_report

def _e(v: Any) -> str:
    return html.escape(redact_text_for_report(str(v if v is not None else "")), quote=True)

def _f(v: Any) -> str:
    return "Unavailable" if v is None else (f"{v:.4f}" if isinstance(v, float) else str(v))

def _j(v: Any) -> str:
    return _e(json.dumps(v, indent=2, ensure_ascii=False, default=str))

def _rows(headers: list[str], rows: list[list[Any]]) -> str:
    h = "".join(f"<th>{_e(x)}</th>" for x in headers)
    b = "".join("<tr>" + "".join(f"<td>{_e(x)}</td>" for x in r) + "</tr>" for r in rows)
    return f"<table><tr>{h}</tr>{b or '<tr><td colspan=\"%d\">Unavailable / insufficient evidence</td></tr>' % len(headers)}</table>"

def _s(title: str, body: str) -> str:
    return f"<section><h2>{_e(title)}</h2>{body}</section>"

def render_run_html(payload: Mapping[str, Any]) -> str:
    m = payload.get("manifest") or {}; x = payload.get("metrics") or {}
    q = x.get("quality") or {}; fp = payload.get("failure_fingerprint") or {}
    ev = str(m.get("evidence_class") or x.get("evidence_class") or "MEASURED")
    badge = "MOCK / SYNTHETIC — NOT REAL BENCHMARK EVIDENCE" if ev in {"MOCK", "DEMO", "DEMONSTRATION"} else ev
    model = m.get("model") or {}; backend = m.get("backend") or {}; dataset = m.get("dataset") or {}
    ci = (x.get("confidence_intervals") or {}).get("quality_mean") or {}
    cards = [("Evidence", ev), ("Total", x.get("n_total")), ("Successful", x.get("n_successful")), ("Failed", x.get("n_failed")), ("Skipped", x.get("n_skipped")), ("Mean quality", q.get("mean"))]
    card_html = "".join(f"<div class='card'><b>{_e(k)}</b><strong>{_e(_f(v))}</strong></div>" for k, v in cards)
    p = [f"<header><h1>LLM Evaluation Run Report</h1><div class='badge'>{_e(badge)}</div></header><div class='cards'>{card_html}</div>"]
    p.append(_s("Provenance and configuration", _rows(["Field", "Value"], [["Run", m.get("run_id")], ["UTC", m.get("utc")], ["Dataset", dataset.get("path")], ["Dataset hash", dataset.get("hash")], ["Task", dataset.get("tasks")], ["Episodes", (x.get("system") or {}).get("episode_count")], ["Model", model.get("model_id")], ["Revision", model.get("model_revision")], ["Backend/device", f"{model.get('adapter_kind')} / {backend.get('device')}"], ["Config hash", m.get("config_hash")], ["Git", (m.get("git") or {}).get("commit")]])))
    p.append(_s("Quality and confidence", _rows(["Metric", "Value", "n"], [["Mean", q.get("mean"), q.get("n_scored")], ["Accuracy", q.get("accuracy"), q.get("n_scored")], ["Std dev", q.get("std"), q.get("n_scored")], ["95% CI", f"{_f(ci.get('lo'))} – {_f(ci.get('hi'))}", ci.get("n")]])))
    if x.get("baseline_comparison"): p.append(_s("Baseline/candidate comparison", f"<pre>{_j(x['baseline_comparison'])}</pre>"))
    for key, title in (("system", "RAG/agent and tool-use metrics"), ("safety", "Safety and risk"), ("deployment", "Cost, latency, and deployment")):
        if x.get(key): p.append(_s(title, _rows(["Metric", "Value"], [[k, v] for k, v in x[key].items()])))
    if x.get("pareto") or x.get("selection"): p.append(_s("Pareto/selection", f"<pre>{_j(x.get('pareto') or x.get('selection'))}</pre>"))
    gate = x.get("release_gate") or {}; reasons = "".join(f"<li>{_e(v)}</li>" for v in gate.get("reasons") or [])
    p.append(_s("Release gate", f"<p><b>Status:</b> {_e(gate.get('status', 'INCONCLUSIVE'))}</p><ul>{reasons}</ul>"))
    p.append(_s("Failure fingerprint", _rows(["Metric", "Value"], [["Failures", fp.get("n_failures")], ["Rate", fp.get("failure_rate")], ["Safety-critical", fp.get("safety_critical_failures")], ["Condition-sensitive", len(fp.get("condition_sensitive_failures") or [])], ["Top priority", fp.get("top_investigation_priority")]]) + f"<pre>{_j({'categories': fp.get('by_category', {}), 'severity': fp.get('by_severity', {}), 'baseline': fp.get('baseline_comparison')})}</pre>"))
    examples = fp.get("representative_sanitized_examples") or (payload.get("failures") or [])[:10]
    details = "".join(f"<details><summary>{_e(v.get('failure_id') or v.get('example_id') or v.get('episode_id') or v.get('test_id'))}</summary><pre>{_j(v)}</pre></details>" for v in examples)
    p += [_s("Representative sanitized failures", details or "<p>Unavailable / no representative failures.</p>"), _s("Missing evidence and limitations", "<p>Unavailable values are not measured zero. Failure patterns are observations, not causal conclusions. Automated checks are not safety certification.</p>"), _s("Reproduction", f"<pre>{_e(m.get('entrypoint_command', 'Unavailable'))}</pre>")]
    css = "body{font:15px system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#172033;background:#f7f9fc}section{background:#fff;border:1px solid #dbe2ea;border-radius:8px;padding:1rem;margin:1rem 0}.cards{display:flex;flex-wrap:wrap;gap:.5rem}.card{background:#eef5ff;border:1px solid #c8dcf7;border-radius:8px;padding:.6rem .9rem}.card strong{display:block;font-size:1.2rem}.badge{background:#fff1bf;border:1px solid #d7ae2a;padding:.5rem;font-weight:700}table{border-collapse:collapse;width:100%}th,td{border:1px solid #dbe2ea;padding:.45rem;text-align:left;vertical-align:top}th{background:#eef2f7}pre{white-space:pre-wrap;overflow:auto;background:#101827;color:#d7e2f0;padding:.8rem;border-radius:6px}"
    return "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Evaluation report</title><style>" + css + "</style></head><body>" + "".join(p) + "</body></html>\n"

__all__ = ["render_run_html"]
