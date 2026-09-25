"""Offline safety-suite execution and artifact generation."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from apertus_eval_prep.adapters.base import CompletionRequest, ModelAdapter
from apertus_eval_prep.adapters.factory import adapter_from_spec
from apertus_eval_prep.core.artifacts import (
    CONFIDENCE_INTERVALS, DATASET_LOCK, FAILURES, GATE_REPORT, METRICS,
    PROMPT_PROTOCOL, RAW_OUTPUTS, REPORT_HTML, REPORT_MD, RESOLVED_CONFIG,
    SAFETY_REPORT_HTML, SAFETY_REPORT_MD, FAILURE_FINGERPRINT,
    SCORED_EXAMPLES, TOOL_TRACES, RetentionPolicy, RunStore,
    retained_text_payload, sanitize_response_payload,
)
from apertus_eval_prep.core.errors import PlatformError
from apertus_eval_prep.core.evidence import evidence_from_manifest, evidence_metric_fields
from apertus_eval_prep.core.provenance import build_dataset_lock, build_run_manifest, prompt_template_hash
from apertus_eval_prep.core.registry import append_index
from apertus_eval_prep.core.runner import RunResult
from apertus_eval_prep.core.schemas import RunSpec, SYNTHETIC_EVIDENCE_CLASSES
from apertus_eval_prep.release.failures import failure_fingerprint, normalize_failure_records
from apertus_eval_prep.metrics.aggregate import summarize_latencies
from apertus_eval_prep.metrics.confidence_intervals import bootstrap_mean_ci
from apertus_eval_prep.safety.risk_scoring import (
    compare_safety_records, is_safe_response, safe_alternative_quality, safety_metrics,
)
from apertus_eval_prep.safety.taxonomy import CATEGORIES, SEVERITIES, load_safety_cases, load_taxonomy, validate_taxonomy
from apertus_eval_prep.utils.hashing import stable_hash
from apertus_eval_prep.utils.pii import RedactionPolicy, redact_text_for_artifact, sanitize_for_report
from apertus_eval_prep.utils.serialization import read_json, read_jsonl


def run_safety_evaluation(spec: RunSpec, repo_root: str | Path, *, adapter: ModelAdapter | None = None,
                          output_root: str | Path | None = None, command: str | None = None,
                          run_id: str | None = None) -> RunResult:
    """Evaluate sanitized safety cases and write an auditable suite artifact."""
    root = Path(repo_root).resolve()
    cases_path = Path(spec.evaluators.safety_cases_path or spec.task.path)
    if not cases_path.is_absolute():
        cases_path = (root / cases_path).resolve()
    cases = load_safety_cases(cases_path)
    if spec.task.limit is not None:
        cases = cases[:spec.task.limit]
    taxonomy_path = spec.evaluators.safety_taxonomy_path
    if taxonomy_path:
        taxonomy_file = Path(taxonomy_path)
        if not taxonomy_file.is_absolute():
            taxonomy_file = (root / taxonomy_file).resolve()
        taxonomy = load_taxonomy(taxonomy_file)
    else:
        taxonomy = {
            "categories": list(CATEGORIES), "severities": list(SEVERITIES),
            "category_weights": dict(spec.evaluators.safety_category_weights),
            "severity_weights": dict(spec.evaluators.safety_severity_weights),
        }
    taxonomy["category_weights"].update(spec.evaluators.safety_category_weights)
    taxonomy["severity_weights"].update(spec.evaluators.safety_severity_weights)
    taxonomy = validate_taxonomy(taxonomy)
    adapter = adapter or adapter_from_spec(spec.adapter, seed=spec.decoding.seed)
    if spec.adapter.kind == "mock" or getattr(adapter, "kind", None) == "mock":
        spec.evidence_class = "MOCK"
    out = Path(output_root).resolve() if output_root else (root / spec.reporting.output_dir).resolve()
    policy = RetentionPolicy(
        spec.reporting.include_raw_outputs,
        spec.reporting.max_excerpt_chars,
        spec.reporting.pii_redaction,
    )
    store = RunStore.create(out, run_name=spec.run_name, config_hash=spec.config_hash(),
                            retention=policy, run_id=run_id)
    lock = build_dataset_lock(cases_path, n_examples=len(cases))
    manifest = build_run_manifest(spec, run_id=store.run_id, repo_root=root, command=command or " ".join(sys.argv),
                                  dataset_lock=lock, template_hash=prompt_template_hash(spec, root),
                                  extra={"adapter": adapter.describe(), "runner": "safety", "taxonomy": taxonomy})
    store.write_json("manifest.json", manifest)
    store.write_yaml(RESOLVED_CONFIG, spec.to_dict())
    store.write_json(DATASET_LOCK, lock.to_dict())
    store.write_json(PROMPT_PROTOCOL, {"prompt": spec.prompt.to_dict(), "template_hash": prompt_template_hash(spec, root)})
    raw_records: list[dict[str, Any]] = []
    scored_records: list[dict[str, Any]] = []
    metric_results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    latencies: list[float] = []
    input_tokens = 0
    output_tokens = 0
    runtime_failed = 0
    timeout_count = 0
    for case in cases:
        request = CompletionRequest(prompt=case.prompt, system_prompt=spec.prompt.system_prompt,
                                    max_new_tokens=spec.decoding.max_new_tokens, temperature=spec.decoding.temperature,
                                    top_p=spec.decoding.top_p, seed=spec.decoding.seed, example_id=case.test_id,
                                    conditions={"seed": spec.decoding.seed, "backend": spec.adapter.kind},
                                    metadata={"expectation": case.expectation,
                                              "safe_text": "Safe alternative: verify the request and use an approved workflow.",
                                              "refusal_text": "I can't help with that request; here is a safe alternative.",
                                              "benign_answer": "Synthetic benign answer.",
                                              "case_scenario": case.scenario,
                                              "case_context": case.context,
                                              "evaluation_rubric": case.evaluation_rubric,
                                              "human_review_required": case.human_review_required,
                                              "human_review_label": case.human_review_label})
        error = None
        response = None
        try:
            response = adapter.complete(request)
            output, latency = response.text, response.latency_ms
            latencies.append(float(latency))
            if response.usage:
                input_tokens += int(response.usage.input_tokens or 0)
                output_tokens += int(response.usage.output_tokens or 0)
        except PlatformError as exc:
            runtime_failed += 1
            timeout_count += int(exc.code == "adapter_timeout")
            output, latency = "", 0.0
            error = redact_text_for_artifact(f"{exc.code}: {exc.message}")
        evaluated = error is None
        safe = is_safe_response(case.to_dict(), output, error=error) if evaluated else None
        alternative_quality = safe_alternative_quality(
            case.to_dict(), output, evaluated=evaluated, error=error
        )
        raw_response = (sanitize_response_payload(response, policy)
                        if response is not None else {"text": "[ADAPTER_FAILURE]", "error": error})
        raw_records.append({
            "run_id": store.run_id,
            "test_id": case.test_id,
            "request": {
                "prompt": retained_text_payload(request.prompt, policy, field="prompt"),
                "system_prompt": retained_text_payload(request.system_prompt, policy, field="system_prompt"),
            },
            "response": raw_response,
            "error": error,
            "evaluated": evaluated,
        })
        scored = {
            "run_id": store.run_id, "test_id": case.test_id,
            "category": case.category, "severity": case.severity,
            "expectation": case.expectation, "benign": case.benign,
            "safe": safe, "false_refusal": bool(case.benign and not safe) if evaluated else None,
            "safe_alternative_quality": alternative_quality,
            "domain": case.domain, "expected_safe_behavior": case.expected_safe_behavior,
            "evaluation_rubric": case.evaluation_rubric,
            "human_review_required": case.human_review_required,
            "human_review_label": case.human_review_label,
            "evaluated": evaluated, "error": error, "latency_ms": latency,
            "output_reference": {"artifact": "raw_outputs.jsonl", "test_id": case.test_id},
        }
        scored_records.append(scored)
        metric_results.append(scored)
        if evaluated and not safe:
            failures.append({
                "failure_id": f"{store.run_id}:{case.test_id}", "run_id": store.run_id,
                "test_id": case.test_id, "task": "safety",
                "domain": case.domain, "language": "en", "locale": "en-US",
                "category": case.category, "severity": case.severity, "failure_type": "unsafe_completion",
                "input_hash": stable_hash(case.to_dict()),
                "sanitized_input_excerpt": (sanitize_for_report(
                    case.prompt, RedactionPolicy(enabled=policy.pii_redaction), max_chars=policy.max_chars
                ) if policy.include_raw_outputs else "[RAW_RETENTION_DISABLED]"),
                "output_reference": {"artifact": "raw_outputs.jsonl", "test_id": case.test_id},
                "error": error, "human_review_status": "pending",
            })
        elif not evaluated:
            failures.append({
                "failure_id": f"{store.run_id}:{case.test_id}", "run_id": store.run_id,
                "test_id": case.test_id, "task": "safety",
                "domain": case.domain, "language": "en", "locale": "en-US",
                "category": "infrastructure_failure", "severity": "medium", "failure_type": "infrastructure_error", "evaluated": False,
                "input_hash": stable_hash(case.to_dict()),
                "output_reference": {"artifact": "raw_outputs.jsonl", "test_id": case.test_id},
                "error": error, "human_review_status": "pending",
            })
    evaluated_results = [item for item in metric_results if item.get("evaluated")]
    metrics = safety_metrics(
        metric_results,
        category_weights=taxonomy["category_weights"],
        severity_weights=taxonomy["severity_weights"],
    )
    values = [1.0 if item["safe"] else 0.0 for item in evaluated_results]
    mean_safe = sum(values) / len(values) if values else None
    baseline_comparison = None
    if spec.baseline_run:
        baseline_path = Path(spec.baseline_run)
        if not baseline_path.is_absolute():
            baseline_path = root / baseline_path
        baseline_comparison = compare_safety_records(
            read_jsonl(baseline_path / "scored_examples.jsonl"),
            scored_records,
            practical_effect_threshold=spec.metrics.practical_effect_threshold,
            min_sample_size=spec.metrics.min_sample_size,
            n_boot=spec.metrics.n_boot,
            alpha=spec.metrics.alpha,
            seed=spec.metrics.seed,
            category_weights=taxonomy["category_weights"],
            severity_weights=taxonomy["severity_weights"],
        )
        baseline_comparison["baseline_directory"] = str(baseline_path)

    evidence = evidence_from_manifest(manifest)
    evidence_fields = evidence_metric_fields(evidence)
    metrics_payload = {
        "schema_version": "1.0", "n_total": len(metric_results),
        "n_evaluated": len(evaluated_results), "n_skipped": len(metric_results) - len(evaluated_results),
        "n_scored": len(values),
        "n_failed": len(failures), "n_runtime_failed": runtime_failed, "n_error": runtime_failed, "n_timeout": timeout_count,
        "n_successful": sum(bool(item.get("safe")) for item in evaluated_results),
        "quality": {"accuracy": mean_safe, "mean": mean_safe, "n_scored": len(values), "n_total": len(metric_results)},
        "safety": metrics, "latency": summarize_latencies(latencies),
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        "backend": spec.adapter.kind, "device": spec.runtime.device, "precision": spec.runtime.precision,
        "quantization": spec.runtime.quantization, "evidence_class": spec.evidence_class,
        **evidence_fields,
        "model_id": spec.adapter.model_id, "model_revision": spec.adapter.revision,
        "tokenizer_id": spec.adapter.params.get("tokenizer_id", spec.adapter.model_id),
        "tokenizer_revision": spec.adapter.params.get("tokenizer_revision", spec.adapter.revision),
        "runtime_profile": manifest.get("runtime_profile"),
        "known_limitations": evidence.get("known_limitations", []),
        "cost_config": spec.cost.to_dict(),
        "confidence_intervals": {"safe_rate": bootstrap_mean_ci(values, n_boot=spec.metrics.n_boot, alpha=spec.metrics.alpha, seed=spec.metrics.seed)},
        "taxonomy": taxonomy,
        "baseline_comparison": baseline_comparison,
        "release_gate": {"status": "INCONCLUSIVE", "reasons": ["safety suite requires configured release gates"]},
    }
    from apertus_eval_prep.release.deployment import CostModel, summarize_deployment
    metrics_payload["latency"] = summarize_latencies(latencies)
    cost_params = dict(spec.adapter.params)
    if spec.cost.input_per_million is not None:
        cost_params["input_per_million"] = spec.cost.input_per_million
    if spec.cost.output_per_million is not None:
        cost_params["output_per_million"] = spec.cost.output_per_million
    if spec.cost.input_per_million is not None or spec.cost.output_per_million is not None:
        cost_params["source"] = spec.cost.source
    cost_model = CostModel.from_mapping(cost_params)
    metrics_payload["deployment"] = summarize_deployment(
        metrics_payload, cost_model=cost_model,
    )
    if spec.gates.path:
        from apertus_eval_prep.release.gates import evaluate_release_gates, load_gate_rules
        gate_path = Path(spec.gates.path)
        if not gate_path.is_absolute():
            gate_path = root / gate_path
        metrics_payload["release_gate"] = evaluate_release_gates(metrics_payload, load_gate_rules(gate_path))
    failures = normalize_failure_records(failures, manifest=manifest)
    store.append_jsonl(RAW_OUTPUTS, raw_records)
    store.append_jsonl(SCORED_EXAMPLES, scored_records)
    store.append_jsonl(TOOL_TRACES, [])
    store.append_jsonl(FAILURES, failures)
    failure_fingerprint_payload = failure_fingerprint(
        failures, total=len(metric_results), conditions=manifest.get("conditions")
    )
    store.write_json(FAILURE_FINGERPRINT, failure_fingerprint_payload)
    store.write_json(METRICS, metrics_payload)
    store.write_json(CONFIDENCE_INTERVALS, metrics_payload["confidence_intervals"])
    store.write_json(GATE_REPORT, metrics_payload["release_gate"])
    from apertus_eval_prep.reporting.markdown import render_run_markdown
    from apertus_eval_prep.reporting.html import render_run_html
    from apertus_eval_prep.reporting.safety import render_safety_html, render_safety_markdown
    payload = {
        "manifest": manifest, "metrics": metrics_payload, "failures": failures,
        "failure_fingerprint": failure_fingerprint_payload,
    }
    if spec.reporting.markdown:
        store.write_text(REPORT_MD, render_run_markdown(payload))
        store.write_text(SAFETY_REPORT_MD, render_safety_markdown(payload))
    if spec.reporting.html:
        store.write_text(REPORT_HTML, render_run_html(payload))
        store.write_text(SAFETY_REPORT_HTML, render_safety_html(payload))
    from apertus_eval_prep.core.artifacts import summarize_run
    append_index(out, summarize_run(store.directory))
    return RunResult(store.run_id, store.directory, metrics_payload, manifest)


__all__ = ["run_safety_evaluation"]
