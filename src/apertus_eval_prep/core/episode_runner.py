"""Offline RAG/agent episode execution with auditable tool traces."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from apertus_eval_prep.adapters.base import CompletionRequest, ModelAdapter, ToolSpecView
from apertus_eval_prep.adapters.factory import adapter_from_spec
from apertus_eval_prep.adapters.mock import MockAdapter
from apertus_eval_prep.core.artifacts import (
    CONFIDENCE_INTERVALS, DATASET_LOCK, FAILURES, GATE_REPORT, METRICS,
    PROMPT_PROTOCOL, RAW_OUTPUTS, REPORT_HTML, REPORT_MD, RESOLVED_CONFIG,
    SCORED_EXAMPLES, TOOL_TRACES, FAILURE_FINGERPRINT, RetentionPolicy, RunStore,
    retained_text_payload, sanitize_response_payload,
)
from apertus_eval_prep.core.errors import PlatformError
from apertus_eval_prep.core.provenance import build_dataset_lock, build_run_manifest, prompt_template_hash
from apertus_eval_prep.core.registry import append_index
from apertus_eval_prep.core.schemas import RunSpec, SYNTHETIC_EVIDENCE_CLASSES
from apertus_eval_prep.release.failures import failure_fingerprint, normalize_failure_records
from apertus_eval_prep.evaluators.groundedness import citation_support, groundedness_score
from apertus_eval_prep.evaluators.tool_use import (
    score_recovery, score_tool_use, simulate_tool_result, validate_tool_call,
)
from apertus_eval_prep.metrics.aggregate import summarize_latencies, summarize_scores
from apertus_eval_prep.metrics.confidence_intervals import bootstrap_mean_ci
from apertus_eval_prep.tasks.agent_episode import AgentEpisodeTask
from apertus_eval_prep.tasks.base import TaskExample
from apertus_eval_prep.tasks.rag_episode import Episode, RAGEpisodeTask, ToolTrace, load_episodes
from apertus_eval_prep.utils.hashing import stable_hash
from apertus_eval_prep.utils.pii import RedactionPolicy, redact_structure, redact_text_for_artifact, sanitize_for_report


def _episode_example(episode: Episode) -> TaskExample:
    return TaskExample(example_id=episode.episode_id, task="episode", prompt=episode.user_request,
                       gold=episode.expected_answer, language=episode.language, locale=episode.locale,
                       domain=episode.domain, metadata=episode.to_dict())


def _trace(episode_id: str, step: int, call: Any, validation: dict[str, Any], response: Any,
           execution: dict[str, Any] | None = None) -> dict[str, Any]:
    execution = dict(execution or {})
    failure = execution.get("error_type")
    trace = ToolTrace(
        episode_id=episode_id,
        step=step,
        tool_name=call.name,
        input_arguments=redact_structure(dict(call.arguments)),
        schema_valid=bool(validation.get("valid")),
        schema_validation=dict(validation),
        result_status=str(execution.get("result_status") or "ok"),
        latency_ms=float(response.latency_ms),
        error_type=None if failure is None else str(failure),
        retry_count=int(execution.get("retry_count") or 0),
        recovered=bool(execution.get("recovered")),
        result=redact_structure(dict(execution.get("result") or {})),
    )
    return trace.to_dict()


def run_episode_evaluation(spec: RunSpec, repo_root: str | Path, *,
                           adapter: ModelAdapter | None = None,
                           output_root: str | Path | None = None,
                           command: str | None = None,
                           run_id: str | None = None) -> Any:
    """Run RAG or tool-agent episodes and persist system-level metrics."""
    root = Path(repo_root).resolve()
    data_path = Path(spec.task.path)
    if not data_path.is_absolute():
        data_path = (root / data_path).resolve()
    episodes = load_episodes(
        data_path,
        limit=spec.task.limit,
        episode_ids=spec.task.episode_ids,
        perturbations=spec.task.perturbations,
    )
    task = RAGEpisodeTask() if spec.task.kind == "rag_episode" else AgentEpisodeTask()
    adapter = adapter or adapter_from_spec(spec.adapter, seed=spec.decoding.seed)
    if isinstance(adapter, MockAdapter):
        adapter.set_oracle({e.episode_id: e.expected_answer or "" for e in episodes})
    if spec.adapter.kind == "mock" or getattr(adapter, "kind", None) == "mock":
        spec.evidence_class = "MOCK"
    config_hash = spec.config_hash()
    policy = RetentionPolicy(spec.reporting.include_raw_outputs, spec.reporting.max_excerpt_chars,
                             spec.reporting.pii_redaction)
    root_out = Path(output_root).resolve() if output_root else (root / spec.reporting.output_dir).resolve()
    store = RunStore.create(root_out, run_name=spec.run_name, config_hash=config_hash,
                            retention=policy, run_id=run_id)
    lock = build_dataset_lock(data_path, tasks=list(spec.task.tasks), n_examples=len(episodes))
    manifest = build_run_manifest(spec, run_id=store.run_id, repo_root=root,
                                  command=command or " ".join(sys.argv), dataset_lock=lock,
                                  template_hash=prompt_template_hash(spec, root), config_hash=config_hash,
                                  extra={"adapter": adapter.describe(), "runner": spec.task.kind})
    store.write_json("manifest.json", manifest)
    store.write_yaml(RESOLVED_CONFIG, spec.to_dict())
    store.write_json(DATASET_LOCK, lock.to_dict())
    store.write_json(PROMPT_PROTOCOL, {"prompt": spec.prompt.to_dict(), "template_hash": prompt_template_hash(spec, root)})
    all_scores: list[float] = []
    latencies: list[float] = []
    input_tokens = 0
    output_tokens = 0
    raw_records: list[dict[str, Any]] = []
    scored_records: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    runtime_failed = 0
    timeout_count = 0
    usage_reported = False
    usage_report_count = 0
    failures: list[dict[str, Any]] = []
    from apertus_eval_prep.release.deployment import CostModel
    cost_params = dict(spec.adapter.params)
    if spec.cost.input_per_million is not None:
        cost_params["input_per_million"] = spec.cost.input_per_million
    if spec.cost.output_per_million is not None:
        cost_params["output_per_million"] = spec.cost.output_per_million
    if spec.cost.input_per_million is not None or spec.cost.output_per_million is not None:
        cost_params["source"] = spec.cost.source
    cost_model = CostModel.from_mapping(cost_params)
    for episode in episodes:
        example = _episode_example(episode)
        episode_input_tokens = 0
        episode_output_tokens = 0
        episode_usage_reported = False
        retrieval_context_count = len(episode.initial_context)
        tools = [ToolSpecView(name=str(item.get("name")), description=str(item.get("description", "")),
                              input_schema=dict(item.get("input_schema") or {})) for item in episode.available_tools]
        metadata = dict(episode.metadata)
        metadata["oracle_answer"] = episode.expected_answer or ""
        metadata["tool_plan"] = episode.tool_plan
        metadata["expected_sources"] = list(episode.expected_sources or episode.expected_citations)
        metadata["expected_citations"] = list(episode.expected_citations or episode.expected_sources)
        metadata.update(episode.to_dict())
        retrieval_failed = bool(metadata.get("retrieval_failed"))
        episode_traces: list[dict[str, Any]] = []
        episode_raw_requests: list[dict[str, Any]] = []
        episode_raw_responses: list[dict[str, Any]] = []
        response = None
        error = None
        for step in range(8):
            request = CompletionRequest(
                prompt=task.prompt_for(example), system_prompt=spec.prompt.system_prompt,
                max_new_tokens=spec.decoding.max_new_tokens, temperature=spec.decoding.temperature,
                top_p=spec.decoding.top_p, seed=spec.decoding.seed, example_id=episode.episode_id,
                conditions={"seed": spec.decoding.seed, "temperature": spec.decoding.temperature,
                            "backend": spec.adapter.kind, "quantization": spec.runtime.quantization},
                tools=tools, metadata=metadata, step=step,
            )
            episode_raw_requests.append({
                "step": step,
                "prompt": retained_text_payload(request.prompt, policy, field="prompt"),
                "system_prompt": retained_text_payload(request.system_prompt, policy, field="system_prompt"),
            })
            try:
                response = adapter.complete(request)
                episode_raw_responses.append(sanitize_response_payload(response, policy))
            except PlatformError as exc:
                runtime_failed += 1
                timeout_count += int(exc.code == "adapter_timeout")
                response = None
                error = redact_text_for_artifact(f"{exc.code}: {exc.message}")
                episode_raw_responses.append({"text": "[ADAPTER_FAILURE]", "error": error})
                break
            latencies.append(float(response.latency_ms))
            if response.usage is not None:
                episode_usage_reported = True
                usage_reported = True
                episode_input_tokens += int(response.usage.input_tokens or 0)
                episode_output_tokens += int(response.usage.output_tokens or 0)
            if not response.tool_calls:
                break
            for call in response.tool_calls:
                validation = validate_tool_call(call.to_dict(), episode.available_tools)
                execution = simulate_tool_result(
                    call.to_dict(), validation, episode_id=episode.episode_id, step=step,
                    metadata=metadata, previous_traces=episode_traces,
                )
                trace = _trace(episode.episode_id, step, call, validation, response, execution)
                episode_traces.append(trace)
                traces.append(trace)
        output = response.text if response is not None else ""
        if error or response is None:
            citation = {
                "citation_count": None, "known_citations": [], "unknown_citations": [],
                "expected_sources": list(episode.expected_source_ids), "supported_expected_sources": [],
                "expected_source_coverage": None, "citation_precision": None,
                "method": "not_evaluated", "uncertainty": "adapter failure; no citation claim made",
            }
            score = {"score": None, "correct": False, "predicted": None,
                     "gold": example.gold, "scorer": "runtime_failure"}
            ground = {"score": None, "supported_token_fraction": None,
                      "unsupported_claim_rate": None, "method": "not_evaluated",
                      "uncertainty": "adapter failure; no groundedness claim made"}
        else:
            score = task.score(example, output)
            ground = groundedness_score(
                output, episode.initial_context,
                threshold=spec.evaluators.groundedness_overlap_threshold,
            )
            citation = citation_support(
                output, episode.initial_context, episode.expected_source_ids
            )
        tool_metric = score_tool_use(episode_traces, expected_tools=[str(x.get("name")) for x in episode.tool_plan])
        tool_metric["recovery"] = score_recovery(episode_traces)
        step_count = len(episode_raw_responses)
        if episode_usage_reported:
            usage_report_count += 1
        input_tokens += episode_input_tokens
        output_tokens += episode_output_tokens
        episode_latency_ms = sum(float(t.get("latency_ms") or 0.0) for t in episode_traces) + (float(response.latency_ms) if response is not None else 0.0)
        unsafe_action_observed = bool(metadata.get("unsafe_action_observed")) or any(
            isinstance(trace.get("result"), Mapping) and bool(trace["result"].get("unsafe_action"))
            for trace in episode_traces
        )
        episode_cost = cost_model.estimate(
            episode_input_tokens if episode_usage_reported else None,
            episode_output_tokens if episode_usage_reported else None,
        )
        raw_records.append({
            "run_id": store.run_id,
            "episode_id": episode.episode_id,
            "step_count": len(episode_raw_responses),
            "requests": episode_raw_requests,
            "responses": episode_raw_responses,
        })
        scored = {
            "run_id": store.run_id,
            "episode_id": episode.episode_id,
            "task": spec.task.kind,
            "score": score.get("score"),
            "correct": bool(score.get("correct")),
            "gold": score.get("gold"),
            "groundedness": ground,
            "citation_support": citation,
            "source_support": {
                "expected_source_coverage": citation.get("expected_source_coverage"),
                "citation_precision": citation.get("citation_precision"),
                "known_citation_count": len(citation.get("known_citations") or []),
            },
            "tool_use": tool_metric,
            "unsafe_action": unsafe_action_observed,
            "expected_unsafe_action": bool(episode.success_criteria.get("unsafe_action", False)),
            "retrieval_failed": retrieval_failed,
            "retrieval_context_count": retrieval_context_count,
            "error": error,
            "latency_ms": response.latency_ms if response is not None else None,
            "end_to_end_latency_ms": episode_latency_ms,
            "step_count": step_count,
            "tool_call_count": tool_metric.get("tool_call_count", 0),
            "unnecessary_tool_call_count": tool_metric.get("unnecessary_tool_call_count", 0),
            "recovery_success_rate": tool_metric.get("recovery", {}).get("recovery_success_rate"),
            "input_tokens": episode_input_tokens if episode_usage_reported else None,
            "output_tokens": episode_output_tokens if episode_usage_reported else None,
            "token_count": (episode_input_tokens + episode_output_tokens) if episode_usage_reported else None,
            "usage_reported": episode_usage_reported,
            "cost_estimate": episode_cost,
            "output_reference": {"artifact": "raw_outputs.jsonl", "episode_id": episode.episode_id},
        }
        scored_records.append(scored)
        if score.get("score") is not None:
            all_scores.append(float(score["score"]))
        if not scored["correct"] or error:
            recovery = tool_metric.get("recovery") or {}
            if error:
                failure_type = "infrastructure_error"
            elif recovery.get("failed_steps") and not recovery.get("recovery_success_rate"):
                failure_type = "tool_recovery_failure"
            elif tool_metric.get("schema_validity_rate") == 0:
                failure_type = "tool_schema_failure"
            elif tool_metric.get("sequence_validity_rate") == 0:
                failure_type = "tool_sequence_failure"
            elif retrieval_failed:
                failure_type = "retrieval_distractor_failure"
            else:
                failure_type = "incorrect_answer"
            failures.append({"failure_id": f"{store.run_id}:{episode.episode_id}", "run_id": store.run_id,
                             "episode_id": episode.episode_id, "task": spec.task.kind,
                             "domain": episode.domain, "language": episode.language, "locale": episode.locale,
                             "category": "episode_failure", "severity": "medium", "failure_type": failure_type,
                             "condition_labels": ["prompt_sensitive_failure"] if episode.metadata.get("perturbation") in {"sanitized_prompt_injection"} else [],
                             "input_hash": stable_hash(episode.to_dict()),
                             "sanitized_input_excerpt": (
                                 sanitize_for_report(episode.user_request, RedactionPolicy(enabled=policy.pii_redaction), max_chars=policy.max_chars)
                                 if policy.include_raw_outputs else "[RAW_RETENTION_DISABLED]"
                             ),
                             "output_reference": {"artifact": "raw_outputs.jsonl", "episode_id": episode.episode_id},
                             "source_reference": {"expected_sources": list(episode.expected_sources or episode.expected_citations)},
                             "trace_reference": "tool_traces.jsonl", "error": error, "evaluated": error is None,
                             "human_review_status": "pending",
                             "suggested_reproduction_command": "apertus-eval-prep platform-episode --config <config>",
                             "tags": ["episode"]})
    store.append_jsonl(RAW_OUTPUTS, raw_records)
    store.append_jsonl(SCORED_EXAMPLES, scored_records)
    store.append_jsonl(TOOL_TRACES, traces)
    failures = normalize_failure_records(failures, manifest=manifest)
    store.append_jsonl(FAILURES, failures)
    failure_fingerprint_payload = failure_fingerprint(
        failures, total=len(episodes), conditions=manifest.get("conditions")
    )
    store.write_json(FAILURE_FINGERPRINT, failure_fingerprint_payload)
    quality = summarize_scores(all_scores, total=len(episodes), failed=len(failures), evidence_class=spec.evidence_class)
    latency_metrics = summarize_latencies(latencies)
    if latencies and output_tokens:
        latency_metrics["throughput"] = output_tokens / (sum(latencies) / 1000.0)
    tool_schema_values = [r["tool_use"].get("schema_validity_rate") for r in scored_records]
    tool_sequence_values = [r["tool_use"].get("sequence_validity_rate") for r in scored_records]
    recovery_values = [r["tool_use"].get("recovery", {}).get("recovery_success_rate") for r in scored_records]
    source_coverage_values = [r.get("source_support", {}).get("expected_source_coverage") for r in scored_records]
    system = {"episode_count": len(episodes), "task_completion_rate": quality["mean"],
              "groundedness_mean": summarize_scores([r["groundedness"].get("score") for r in scored_records], total=len(scored_records))["mean"],
              "tool_schema_validity": summarize_scores(tool_schema_values, total=len(scored_records))["mean"],
              "tool_sequence_validity": summarize_scores(tool_sequence_values, total=len(scored_records))["mean"],
              "tool_call_efficiency": summarize_scores([r["tool_use"]["tool_call_efficiency"] for r in scored_records], total=len(scored_records))["mean"],
              "tool_call_count": sum(r.get("tool_call_count", 0) for r in scored_records),
              "unnecessary_tool_call_count": sum(r.get("unnecessary_tool_call_count", 0) for r in scored_records),
              "recovery_success_rate": summarize_scores(recovery_values, total=len(scored_records))["mean"],
              "step_count_mean": (sum(r.get("step_count", 0) for r in scored_records) / len(scored_records)) if scored_records else None,
              "step_count_total": sum(r.get("step_count", 0) for r in scored_records),
              "end_to_end_latency_ms_mean": summarize_latencies([r.get("end_to_end_latency_ms") for r in scored_records])["mean_ms"],
              "unsupported_claim_rate": summarize_scores([r["groundedness"].get("unsupported_claim_rate") for r in scored_records], total=len(scored_records))["mean"],
              "source_citation_coverage": summarize_scores(source_coverage_values, total=len(scored_records))["mean"],
               "usage_reported": usage_reported,
               "retrieval_failure_count": sum(bool(r.get("retrieval_failed")) for r in scored_records),
               "retrieval_context_count_mean": summarize_scores([r.get("retrieval_context_count") for r in scored_records], total=len(scored_records))["mean"],
               "usage_report_count": usage_report_count,
               "usage_complete": bool(scored_records) and usage_report_count == len(scored_records),

               "input_tokens": input_tokens if usage_reported else None,
               "output_tokens": output_tokens if usage_reported else None,
               "token_count": (input_tokens + output_tokens) if usage_reported else None,

              "unsafe_action_count": sum(bool(r.get("unsafe_action")) for r in scored_records)}

    metrics = {"schema_version": "1.0", "n_total": len(episodes), "n_scored": quality["n_scored"],
               "n_failed": len(failures), "n_runtime_failed": runtime_failed, "n_error": runtime_failed, "n_timeout": timeout_count,
               "n_successful": sum(bool(item.get("correct")) for item in scored_records), "quality": quality, "system": system,
               "confidence_intervals": {"quality_mean": bootstrap_mean_ci(all_scores, n_boot=spec.metrics.n_boot, alpha=spec.metrics.alpha, seed=spec.metrics.seed)},
               "latency": latency_metrics,
               "usage": {"input_tokens": input_tokens if usage_reported else None,
                          "output_tokens": output_tokens if usage_reported else None,
                          "token_count": (input_tokens + output_tokens) if usage_reported else None,
                          "reported": usage_reported,
                          "reported_episodes": usage_report_count,
                          "complete": bool(episodes) and usage_report_count == len(episodes)},
               "backend": spec.adapter.kind, "device": spec.runtime.device, "precision": spec.runtime.precision,
               "quantization": spec.runtime.quantization,
               "evidence_class": spec.evidence_class, "synthetic_or_mock": spec.evidence_class in SYNTHETIC_EVIDENCE_CLASSES,
               "release_gate": {"status": "INCONCLUSIVE", "reasons": ["episode evidence is not a release certification"]}}
    from apertus_eval_prep.release.deployment import summarize_deployment
    metrics["deployment"] = summarize_deployment(metrics, cost_model=cost_model)
    if spec.gates.path:
        from apertus_eval_prep.release.gates import evaluate_release_gates, load_gate_rules
        gate_path = Path(spec.gates.path)
        if not gate_path.is_absolute():
            gate_path = root / gate_path
        metrics["release_gate"] = evaluate_release_gates(metrics, load_gate_rules(gate_path))
    store.write_json(METRICS, metrics)
    store.write_json(CONFIDENCE_INTERVALS, metrics["confidence_intervals"])
    store.write_json(GATE_REPORT, metrics["release_gate"])
    payload = {
        "manifest": manifest, "metrics": metrics, "failures": failures,
        "failure_fingerprint": failure_fingerprint_payload,
    }
    from apertus_eval_prep.reporting.markdown import render_run_markdown
    from apertus_eval_prep.reporting.html import render_run_html
    if spec.reporting.markdown:
        store.write_text(REPORT_MD, render_run_markdown(payload))
    if spec.reporting.html:
        store.write_text(REPORT_HTML, render_run_html(payload))
    from apertus_eval_prep.core.runner import RunResult
    from apertus_eval_prep.core.artifacts import summarize_run
    append_index(root_out, summarize_run(store.directory))
    return RunResult(store.run_id, store.directory, metrics, manifest)


__all__ = ["run_episode_evaluation"]
