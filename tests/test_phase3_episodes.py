from __future__ import annotations

import json
from pathlib import Path

import pytest

from apertus_eval_prep.adapters.mock import MockAdapter
from apertus_eval_prep.core.config import load_run_spec
from apertus_eval_prep.core.runner import run_evaluation
from apertus_eval_prep.evaluators.groundedness import citation_support, groundedness_score
from apertus_eval_prep.evaluators.tool_use import (
    score_recovery,
    score_tool_sequence,
    score_tool_use,
    simulate_tool_result,
    validate_tool_call,
)
from apertus_eval_prep.tasks.perturbations import PERTURBATIONS, apply_perturbation
from apertus_eval_prep.tasks.rag_episode import Episode, ToolTrace, load_episodes
from apertus_eval_prep.utils.pii import redact_text_for_report
from apertus_eval_prep.utils.serialization import read_json, read_jsonl

ROOT = Path(__file__).resolve().parents[1]


def test_episode_schema_accepts_aliases_and_exposes_optional_dimensions():
    episode = Episode.from_mapping({
        "id": "schema-1",
        "prompt": "Answer using the supplied context.",
        "documents": [{"source_id": "s1", "content": "Approved answer."}],
        "tools": [{"name": "lookup", "input_schema": {"required": ["id"]}}],
        "expected_constraints": ["Stay grounded."],
        "success_criteria": {"task_completed": True},
        "expected_sources": ["s1"],
        "language": "en",
        "locale": "en-US",
        "domain": "policy",
    })
    assert episode.episode_id == "schema-1"
    assert episode.documents == episode.initial_context
    assert episode.available_tools[0]["name"] == "lookup"
    assert episode.expected_source_ids == ["s1"]
    assert episode.locale == "en-US"


def test_report_redaction_preserves_numeric_metrics():
    text = "contact person@example.com; token=abcdef123456; latency 117.6142"
    redacted = redact_text_for_report(text)
    assert "person@example.com" not in redacted
    assert "abcdef123456" not in redacted
    assert "117.6142" in redacted
    assert "[REDACTED:phone]" not in redacted


def test_tool_trace_round_trip_redacts_arguments_and_results():
    trace = ToolTrace.from_mapping({
        "episode_id": "e1",
        "step_number": 2,
        "tool_name": "lookup",
        "arguments": {"api_key": "sk-abcdefghijklmnop", "id": "x"},
        "result": {"password": "do-not-store", "status": "ok"},
        "schema_valid": True,
        "schema_validation": {"valid": True},
        "latency_ms": 4.5,
    })
    payload = trace.to_dict()
    assert payload["step"] == 1
    assert payload["step_number"] == 2
    assert payload["input_arguments"]["api_key"] == "[REDACTED_FIELD]"
    assert payload["result"]["password"] == "[REDACTED_FIELD]"
    assert "sk-abcdefghijklmnop" not in json.dumps(payload)
    assert "do-not-store" not in json.dumps(payload)


def test_perturbations_are_deterministic_and_safe():
    episode = load_episodes(ROOT / "data/platform_episodes.jsonl")[0]
    base = episode.to_dict()
    for name in PERTURBATIONS:
        first = apply_perturbation(base, name)
        second = apply_perturbation(base, name)
        assert first == second
        assert first["metadata"]["perturbation"]
        assert "rm -rf" not in json.dumps(first)
    assert apply_perturbation(base, "remove_key_evidence")["initial_context"] == []
    assert apply_perturbation(base, "add_irrelevant_distractors")["initial_context"][-1]["source_id"] == "distractor"
    assert apply_perturbation(base, "simulate_tool_timeout")["metadata"]["tool_failure"] == "timeout"
    assert apply_perturbation(base, "simulate_retrieval_failure")["metadata"]["retrieval_failed"] is True
    injected = apply_perturbation(base, "sanitized_retrieval_prompt_injection")
    assert injected["metadata"]["injection_detector"] is True
    assert "Ignore prior instructions" in json.dumps(injected)


def test_tool_and_groundedness_metrics_expose_missingness():
    tools = [{"name": "lookup", "input_schema": {"required": ["id"]}}]
    valid = validate_tool_call({"name": "lookup", "arguments": {"id": "x"}}, tools)
    invalid = validate_tool_call({"name": "lookup", "arguments": {}}, tools)
    assert valid["valid"] is True
    assert invalid["valid"] is False
    traces = [
        {"tool_name": "lookup", "schema_valid": True},
        {"tool_name": "extra", "schema_valid": True},
    ]
    tool_score = score_tool_use(traces, expected_tools=["lookup"])
    assert tool_score["tool_call_count"] == 2
    assert tool_score["unnecessary_tool_call_count"] == 1
    assert score_tool_sequence(traces, ["lookup"])["valid"] is False
    failure = simulate_tool_result(
        {"name": "lookup", "arguments": {"id": "x"}}, valid,
        episode_id="e1", step=0, metadata={"tool_failure": "timeout"},
    )
    recovered = simulate_tool_result(
        {"name": "lookup", "arguments": {"id": "x"}}, valid,
        episode_id="e1", step=1, metadata={"tool_failure": "timeout"},
        previous_traces=[{"tool_name": "lookup", "error_type": "timeout"}],
    )
    assert failure["result_status"] == "timeout"
    assert recovered["result_status"] == "ok"
    assert recovered["recovered"] is True
    assert score_recovery([{"result_status": "timeout", "error_type": "timeout"},
                          {"result_status": "ok", "recovered": True}])["recovery_success_rate"] == 1.0
    ground = groundedness_score(
        "The approved response is two business days [policy-v3]",
        [{"source_id": "policy-v3", "content": "The approved response is two business days."}],
    )
    citation = citation_support(
        "The approved response is two business days [policy-v3]",
        [{"source_id": "policy-v3", "content": "The approved response is two business days."}],
        ["policy-v3"],
    )
    assert ground["score"] > 0.5
    assert citation["expected_source_coverage"] == 1.0
    assert citation["citation_precision"] == 1.0
    assert groundedness_score("", [{"content": "anything"}])["unsupported_claim_rate"] == 1.0


def _assert_phase3_artifacts(result, expected_episodes: int = 5):
    directory = result.directory
    required = {"manifest.json", "config.resolved.yaml", "raw_outputs.jsonl",
                "scored_examples.jsonl", "tool_traces.jsonl", "metrics.json",
                "failures.jsonl", "report.md", "report.html"}
    assert required.issubset({path.name for path in directory.iterdir()})
    raw = read_jsonl(directory / "raw_outputs.jsonl")
    scored = read_jsonl(directory / "scored_examples.jsonl")
    assert len(raw) == len(scored) == expected_episodes
    assert "output_excerpt" not in scored[0]
    assert "responses" in raw[0]
    system = result.metrics["system"]
    for key in (
        "task_completion_rate", "groundedness_mean", "tool_schema_validity",
        "tool_sequence_validity", "unnecessary_tool_call_count", "recovery_success_rate",
        "step_count_mean", "end_to_end_latency_ms_mean", "unsupported_claim_rate",
        "source_citation_coverage", "unsafe_action_count", "usage_reported",
    ):
        assert key in system
    assert result.metrics["usage"]["reported"] is True
    assert result.metrics["deployment"]["cost"]["quality"] == "UNAVAILABLE"
    report = (directory / "report.md").read_text(encoding="utf-8")
    for section in ("RAG/agent metrics", "tool_schema_validity", "recovery_success_rate",
                    "source_citation_coverage", "Synthetic/mock evidence"):
        assert section in report
    assert "[REDACTED:phone]" not in report
    assert "| end_to_end_latency_ms_mean | 117.6142 |" in report


def test_phase3_rag_end_to_end_writes_auditable_artifacts(tmp_path):
    result = run_evaluation(
        load_run_spec(ROOT / "configs/platform_phase3_rag.yaml"),
        ROOT,
        output_root=tmp_path / "rag",
        command="phase3-rag-test",
    )
    assert result.metrics["evidence_class"] == "MOCK"
    assert result.metrics["system"]["episode_count"] == 5
    _assert_phase3_artifacts(result)
    scored = read_jsonl(result.directory / "scored_examples.jsonl")
    assert any(item["citation_support"]["expected_source_coverage"] == 1.0 for item in scored)


def test_phase3_agent_end_to_end_records_recovery_and_traces(tmp_path):
    result = run_evaluation(
        load_run_spec(ROOT / "configs/platform_phase3_agent.yaml"),
        ROOT,
        output_root=tmp_path / "agent",
        command="phase3-agent-test",
    )
    assert result.metrics["evidence_class"] == "MOCK"
    assert result.metrics["system"]["episode_count"] == 5
    _assert_phase3_artifacts(result)
    traces = read_jsonl(result.directory / "tool_traces.jsonl")
    assert traces
    assert all({"episode_id", "step", "tool_name", "schema_valid", "result_status",
                "latency_ms", "error_type", "retry_count", "recovered"}.issubset(trace)
               for trace in traces)
    recovery = [trace for trace in traces if trace["error_type"] == "timeout"]
    assert recovery and any(trace["recovered"] for trace in traces)
    assert result.metrics["system"]["recovery_success_rate"] == 1.0


def test_phase3_runtime_failure_is_explicitly_unscored(tmp_path):
    spec = load_run_spec(ROOT / "configs/platform_phase3_agent.yaml")
    result = run_evaluation(
        spec, ROOT, adapter=MockAdapter(mode="error"),
        output_root=tmp_path / "error", command="phase3-error-test",
    )
    assert result.metrics["n_runtime_failed"] == 5
    assert result.metrics["n_scored"] == 0
    assert result.metrics["usage"]["reported"] is False
    assert result.metrics["system"]["groundedness_mean"] is None
    scored = read_jsonl(result.directory / "scored_examples.jsonl")
    assert all(item["score"] is None and item["groundedness"]["method"] == "not_evaluated"
               for item in scored)
    assert all(item["citation_support"]["method"] == "not_evaluated" for item in scored)
