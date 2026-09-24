"""Offline-first evaluation runner producing immutable run artifacts."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apertus_eval_prep.adapters.base import CompletionRequest, ModelAdapter
from apertus_eval_prep.adapters.factory import adapter_from_spec
from apertus_eval_prep.adapters.mock import MockAdapter
from apertus_eval_prep.core.artifacts import (
    CONFIDENCE_INTERVALS, DATASET_LOCK, FAILURES, GATE_REPORT, METRICS,
    PROMPT_PROTOCOL, RAW_OUTPUTS, RESOLVED_CONFIG, SCORED_EXAMPLES, TOOL_TRACES,
    FAILURE_FINGERPRINT,
    REPORT_MD, REPORT_HTML, RetentionPolicy, RunStore, retained_text_payload,
    sanitize_response_payload,
)
from apertus_eval_prep.core.config import load_run_spec
from apertus_eval_prep.core.errors import PlatformError
from apertus_eval_prep.core.evidence import evidence_from_manifest, evidence_metric_fields
from apertus_eval_prep.core.provenance import build_dataset_lock, build_run_manifest, prompt_template_hash
from apertus_eval_prep.core.registry import append_index
from apertus_eval_prep.core.schemas import RunSpec, SYNTHETIC_EVIDENCE_CLASSES
from apertus_eval_prep.release.failures import failure_fingerprint, normalize_failure_records
from apertus_eval_prep.evaluators.quality import score_response
from apertus_eval_prep.metrics.aggregate import summarize_latencies, summarize_scores
from apertus_eval_prep.metrics.confidence_intervals import bootstrap_mean_ci
from apertus_eval_prep.tasks.base import TaskBatch, load_task_examples
from apertus_eval_prep.tasks.static_qa import StaticQATask
from apertus_eval_prep.utils.hashing import stable_hash
from apertus_eval_prep.utils.pii import RedactionPolicy, sanitize_for_report


@dataclass(frozen=True)
class RunResult:
    """Public handle returned after a completed run."""

    run_id: str
    directory: Path
    metrics: dict[str, Any]
    manifest: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "directory": str(self.directory),
                "metrics": self.metrics, "manifest": self.manifest}


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (root / path).resolve()


def _conditions(spec: RunSpec) -> dict[str, Any]:
    return {
        "seed": spec.decoding.seed, "temperature": spec.decoding.temperature,
        "top_p": spec.decoding.top_p, "prompt_id": spec.prompt.prompt_id,
        "prompt_template": spec.prompt.template, "prompt_version": spec.prompt.version,
        "system_prompt_sha256": stable_hash(spec.prompt.system_prompt) if spec.prompt.system_prompt else None,
        "system_prompt_present": bool(spec.prompt.system_prompt), "backend": spec.adapter.kind,
        "quantization": spec.runtime.quantization, "precision": spec.runtime.precision,
        "device": spec.runtime.device, **spec.conditions,
    }


def _safe_response(response: Any, *, retain: bool, max_chars: int, pii_redaction: bool = True) -> dict[str, Any]:
    """Compatibility wrapper around the common artifact sanitizer."""
    return sanitize_response_payload(
        response,
        RetentionPolicy(
            include_raw_outputs=retain,
            max_chars=max_chars,
            pii_redaction=pii_redaction,
        ),
    )


def _failure(example: Any, score: dict[str, Any], error: str | None, run_id: str,
             retention: RetentionPolicy) -> dict[str, Any]:
    category = "timeout_or_infrastructure_failure" if error else "incorrect_answer"
    if not score.get("correct", False) and score.get("predicted") is None:
        category = "unparseable_or_empty_output" if not error else category
    return {
        "failure_id": f"{run_id}:{example.example_id}", "run_id": run_id,
        "example_id": example.example_id, "task": example.task,
        "domain": example.domain, "language": example.language, "locale": example.locale,
        "category": category, "severity": "medium",
        "input_hash": stable_hash(example.to_dict(include_prompt=True)),
        "sanitized_input_excerpt": (
            sanitize_for_report(example.prompt, RedactionPolicy(enabled=retention.pii_redaction), max_chars=retention.max_chars)
            if retention.include_raw_outputs else "[RAW_RETENTION_DISABLED]"
        ),
        "output_reference": {"artifact": "raw_outputs.jsonl", "example_id": example.example_id},
        "trace_reference": None, "conditions": {}, "tags": [],
        "evaluated": error is None, "human_review_status": "pending", "error": error,
        "suggested_reproduction_command": "apertus-eval-prep platform-run --config <resolved-config>",
        "reproduction_command": "apertus-eval-prep platform-run --config <config>",
    }


def run_evaluation(
    spec: RunSpec, repo_root: str | Path, *, adapter: ModelAdapter | None = None,
    output_root: str | Path | None = None, command: str | None = None,
    run_id: str | None = None,
) -> RunResult:
    """Execute a static-QA run and persist the complete audit artifact."""
    root = Path(repo_root).resolve()
    if spec.task.kind in {"rag_episode", "agent_episode"}:
        from apertus_eval_prep.core.episode_runner import run_episode_evaluation
        return run_episode_evaluation(spec, root, adapter=adapter, output_root=output_root,
                                      command=command, run_id=run_id)
    if spec.adapter.kind == "mock" or getattr(adapter, "kind", None) == "mock":
        spec.evidence_class = "MOCK"
    data_path = _resolve(root, spec.task.path)
    batch: TaskBatch = load_task_examples(
        data_path, tasks=spec.task.tasks, limit=spec.task.limit, split=spec.task.split
    )
    task = StaticQATask()
    adapter = adapter or adapter_from_spec(spec.adapter, seed=spec.decoding.seed)
    if isinstance(adapter, MockAdapter) and spec.adapter.params.get("oracle_source", "dataset_gold") == "dataset_gold":
        adapter.set_oracle({item.example_id: item.gold or "" for item in batch.examples if item.gold is not None})
    config_hash = spec.config_hash()
    policy = RetentionPolicy(
        include_raw_outputs=spec.reporting.include_raw_outputs,
        max_chars=spec.reporting.max_excerpt_chars,
        pii_redaction=spec.reporting.pii_redaction,
    )
    root_out = Path(output_root).resolve() if output_root else _resolve(root, spec.reporting.output_dir)
    store = RunStore.create(root_out, run_name=spec.run_name, config_hash=config_hash,
                            retention=policy, run_id=run_id)
    dataset_lock = build_dataset_lock(
        data_path, tasks=list(spec.task.tasks), split=spec.task.split, n_examples=len(batch)
    )
    manifest = build_run_manifest(
        spec, run_id=store.run_id, repo_root=root,
        command=command or " ".join(sys.argv), dataset_lock=dataset_lock,
        template_hash=prompt_template_hash(spec, root), config_hash=config_hash,
        extra={"adapter": adapter.describe(), "runner": "static_qa"},
    )
    store.write_json("manifest.json", manifest)
    store.write_yaml(RESOLVED_CONFIG, spec.to_dict())
    store.write_json(DATASET_LOCK, dataset_lock.to_dict())
    store.write_json(PROMPT_PROTOCOL, {
        "prompt": spec.prompt.to_dict(), "template_hash": prompt_template_hash(spec, root),
        "rendered_examples": [item.to_dict(include_prompt=False) for item in batch.examples[:3]],
    })
    store.append_jsonl(TOOL_TRACES, [])
    conditions = _conditions(spec)
    scores: list[float] = []
    latencies: list[float] = []
    input_tokens = 0
    output_tokens = 0
    raw_records: list[dict[str, Any]] = []
    scored_records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    failed = 0
    timeout_count = 0

    for example in batch.examples:
        request = CompletionRequest(
            prompt=task.prompt_for(example), system_prompt=spec.prompt.system_prompt,
            max_new_tokens=spec.decoding.max_new_tokens, temperature=spec.decoding.temperature,
            top_p=spec.decoding.top_p, seed=spec.decoding.seed, example_id=example.example_id,
            conditions=conditions, metadata=task.metadata_for(example), stop=list(spec.decoding.stop),
        )
        error: str | None = None
        response = None
        output = ""
        try:
            response = adapter.complete(request)
            raw = _safe_response(response, retain=policy.include_raw_outputs, max_chars=policy.max_chars,
                                 pii_redaction=policy.pii_redaction)
            output = response.text
            score = score_response(example, output, metadata=example.metadata)
            latencies.append(float(response.latency_ms))
            if response.usage:
                input_tokens += int(response.usage.input_tokens or 0)
                output_tokens += int(response.usage.output_tokens or 0)
        except PlatformError as exc:
            failed += 1
            timeout_count += int(exc.code == "adapter_timeout")
            error = f"{exc.code}: {exc.message}"
            raw = {"text": "[ADAPTER_FAILURE]", "error": error, "error_code": exc.code}
            score = {"score": None, "correct": False, "predicted": None,
                     "scorer": "runtime_failure"}
        raw_records.append({
            "run_id": store.run_id, "example_id": example.example_id,
            "task": example.task, "conditions": conditions,
            "request": {
                "prompt": retained_text_payload(request.prompt, policy, field="prompt"),
                "system_prompt": retained_text_payload(request.system_prompt, policy, field="system_prompt"),
            },
            "response": raw,
        })
        scored = {
            "run_id": store.run_id, "example_id": example.example_id,
            "task": example.task, "language": example.language, "domain": example.domain,
            "score": score.get("score"), "correct": bool(score.get("correct")),
            "predicted": score.get("predicted"), "gold": score.get("gold"),
            "refusal": bool(score.get("refusal")), "error": error,
            "latency_ms": response.latency_ms if response is not None else None,
            "output_reference": {"artifact": "raw_outputs.jsonl", "example_id": example.example_id},
            "scorer": score.get("scorer"),
        }
        scored_records.append(scored)
        if not scored["correct"] or error:
            failure = _failure(example, score, error, store.run_id, policy)
            failure["conditions"] = conditions
            failures.append(failure)
        if scored["score"] is not None:
            scores.append(float(scored["score"]))
    store.append_jsonl(RAW_OUTPUTS, raw_records)
    store.append_jsonl(SCORED_EXAMPLES, scored_records)
    failures = normalize_failure_records(failures, manifest=manifest)
    store.append_jsonl(FAILURES, failures)
    failure_fingerprint_payload = failure_fingerprint(
        failures, total=len(batch), conditions=manifest.get("conditions")
    )
    store.write_json(FAILURE_FINGERPRINT, failure_fingerprint_payload)
    quality = summarize_scores(scores, total=len(batch), failed=len(failures), evidence_class=spec.evidence_class)
    ci = bootstrap_mean_ci(scores, n_boot=spec.metrics.n_boot, alpha=spec.metrics.alpha, seed=spec.metrics.seed)
    latency_metrics = summarize_latencies(latencies)
    if latencies and output_tokens:
        latency_metrics["throughput"] = output_tokens / (sum(latencies) / 1000.0)
    evidence = evidence_from_manifest(manifest)
    evidence_fields = evidence_metric_fields(evidence)
    metrics: dict[str, Any] = {
        "schema_version": "1.0", "n_total": len(batch), "n_scored": quality["n_scored"],
        "n_failed": len(failures), "n_runtime_failed": failed, "n_error": failed, "n_timeout": timeout_count,
        "n_successful": sum(bool(item.get("correct")) for item in scored_records), "quality": quality,
        "confidence_intervals": {"quality_mean": ci}, "latency": latency_metrics,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        "backend": spec.adapter.kind, "device": spec.runtime.device,
        "precision": spec.runtime.precision, "quantization": spec.runtime.quantization,
        "evidence_class": spec.evidence_class,
        **evidence_fields,
        "model_id": spec.adapter.model_id, "model_revision": spec.adapter.revision,
        "tokenizer_id": spec.adapter.params.get("tokenizer_id", spec.adapter.model_id),
        "tokenizer_revision": spec.adapter.params.get("tokenizer_revision", spec.adapter.revision),
        "runtime_profile": manifest.get("runtime_profile"),
        "known_limitations": evidence.get("known_limitations", []),
        "cost_config": spec.cost.to_dict(),
        "release_gate": {"status": "INCONCLUSIVE", "reasons": ["no release-gate policy evaluated"]},
    }
    from apertus_eval_prep.release.deployment import CostModel, summarize_deployment
    cost_params = dict(spec.adapter.params)
    if spec.cost.input_per_million is not None:
        cost_params["input_per_million"] = spec.cost.input_per_million
    if spec.cost.output_per_million is not None:
        cost_params["output_per_million"] = spec.cost.output_per_million
    if spec.cost.input_per_million is not None or spec.cost.output_per_million is not None:
        cost_params["source"] = spec.cost.source
    cost_model = CostModel.from_mapping(cost_params)
    metrics["deployment"] = summarize_deployment(metrics, cost_model=cost_model)
    if spec.gates.path:
        from apertus_eval_prep.release.gates import evaluate_release_gates, load_gate_rules
        gate_path = _resolve(root, spec.gates.path)
        metrics["release_gate"] = evaluate_release_gates(metrics, load_gate_rules(gate_path))

    store.write_json(METRICS, metrics)
    store.write_json(CONFIDENCE_INTERVALS, metrics["confidence_intervals"])
    store.write_json(GATE_REPORT, metrics["release_gate"])
    report_payload = {
        "manifest": manifest, "metrics": metrics, "failures": failures,
        "failure_fingerprint": failure_fingerprint_payload,
    }
    from apertus_eval_prep.reporting.markdown import render_run_markdown
    from apertus_eval_prep.reporting.html import render_run_html
    if spec.reporting.markdown:
        store.write_text(REPORT_MD, render_run_markdown(report_payload))
    if spec.reporting.html:
        store.write_text(REPORT_HTML, render_run_html(report_payload))
    from apertus_eval_prep.core.artifacts import summarize_run
    append_index(root_out, summarize_run(store.directory))
    return RunResult(store.run_id, store.directory, metrics, manifest)


def run_config(
    config_path: str | Path, repo_root: str | Path, *, overrides: dict[str, Any] | None = None,
    output_root: str | Path | None = None, command: str | None = None,
    run_id: str | None = None,
) -> RunResult:
    """Load a YAML run spec and execute it."""
    spec = load_run_spec(config_path, overrides)
    return run_evaluation(spec, repo_root, output_root=output_root, command=command, run_id=run_id)


__all__ = ["RunResult", "run_evaluation", "run_config"]
