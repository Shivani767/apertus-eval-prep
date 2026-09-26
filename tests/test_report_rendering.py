"""Reports must render as HTML and must not lose their own measurements.

Two classes of defect are guarded here:
* redaction that eats measured numbers (a metric such as 0.4736842105263158 used to be
  replaced by a ``card_like`` placeholder, so the headline metric was unreadable), and
* HTML that is really escaped Markdown in a ``<pre>`` block, or a Python ``repr`` of a
  config mapping instead of JSON.
"""
from __future__ import annotations

from apertus_eval_prep.experiments.reporting import render_experiment_html
from apertus_eval_prep.reporting.html import render_run_html
from apertus_eval_prep.reporting.safety import render_safety_html
from apertus_eval_prep.study.reporting import render_study_html
from apertus_eval_prep.utils.pii import redact_text_for_report

LONG_DECIMAL = "0.4736842105263158"


def _run_payload() -> dict:
    return {
        "manifest": {
            "run_id": "run-1",
            "utc": "2026-09-26T12:00:21Z",
            "evidence_class": "LOCAL_REAL_MODEL",
            "evidence": {"mode": "LOCAL_REAL_MODEL", "real_model_execution": True,
                         "runtime_environment": "google_colab", "hardware_measured": True},
            "model": {"model_id": "Qwen/Qwen2.5-3B-Instruct", "model_revision": "main",
                      "adapter_kind": "local_transformers"},
            "backend": {"device": "cuda"},
            "dataset": {"path": "data/eval_set.jsonl", "hash": "a61b133dd0a9ebd4",
                        "tasks": ["arc_easy", "gsm8k"]},
            "config_hash": "3895d1804914d5cd",
            "entrypoint_command": "python -m apertus_eval_prep platform-run",
        },
        "metrics": {
            "n_total": 38, "n_successful": 18, "n_failed": 20, "n_skipped": None,
            "quality": {"mean": float(LONG_DECIMAL), "accuracy": float(LONG_DECIMAL), "std": 0.5, "n_scored": 38},
            "confidence_intervals": {"quality_mean": {"lo": 0.3158, "hi": 0.6315, "n": 38}},
            "deployment": {"cost": {"input_per_million": None, "currency": "USD", "source": "manual_config"}},
            "release_gate": {"status": "BLOCKED_SAFETY", "reasons": ["attack_success_rate=0.6 violates max 0.1"]},
        },
        "failures": [],
        "failure_fingerprint": {"n_failures": 20, "failure_rate": 0.526, "by_category": {"incorrect_answer": 20}},
    }


def _experiment_result() -> dict:
    return {
        "experiment_id": "sarvam_application_real_eval_v1",
        "cells": [],
        "report": {
            "experiment_summary": {"n_ok": 6, "n_cells": 6, "n_examples": 228, "n_error": 0},
            "quality_summary": {"count": 6, "mean": float(LONG_DECIMAL), "std": 0.0,
                                "confidence_interval": {"lo": 0.4, "hi": 0.5}},
            "baseline_vs_first_candidate": {"status": "INCONCLUSIVE", "delta": 0.0, "ci_low": 0.0,
                                            "ci_high": 0.0, "n_paired": 38, "effect_size": 0.0},
            "factor_metrics": {"factors": [{"factor": "seed", "unstable": False, "levels": {
                "11": {"mean": 0.47, "n_scored": 38, "confidence_interval": {"lo": 0.3, "hi": 0.6}}}}]},
            "confidence_intervals": {"cell_quality_mean": {"lo": 0.4, "hi": 0.5}},
            "robust_capability_score": {"mean_quality": 0.47, "configuration_variance": 0.0, "lambda": 1.0,
                                        "score": 0.47, "experimental": True},
            "baseline_cell": "baseline",
            "candidate_cell": "seed=11",
            "unstable_conditions": [],
            "representative_sensitive_failures": [],
            "reproduction_command": "apertus-eval-prep platform-matrix --config local_variance.yaml",
            "limitations": ["RCS is experimental"],
        },
    }


def _study_summary() -> dict:
    return {
        "study": {"study_id": "sarvam_application_real_eval_v1", "study_title": "Phase 8 study",
                  "research_question": "How do configurations differ?", "hypothesis_ids": ["H1"],
                  "planned_sample_counts": {"core": 38}, "protocol_path": "docs/PHASE8_STUDY_PROTOCOL.md",
                  "preregistration_path": "docs/studies/PREREGISTRATION.md"},
        "evidence_modes": ["LOCAL_REAL_MODEL"],
        "real_model_evidence_available": True,
        "rows": [{
            "run_id": "run-1", "model_id": "Qwen/Qwen2.5-3B-Instruct", "model_revision": "main",
            "evidence_mode": "LOCAL_REAL_MODEL", "config_hash": "3895d1804914d5cd",
            "quality": {"mean": float(LONG_DECIMAL)},
            "confidence_intervals": {"quality_mean": {"lo": 0.3158, "hi": 0.6315}},
            "safety": {"attack_success_rate": 0.6},
            "system": {"groundedness_mean": 0.5, "task_completion_rate": 0.2},
            "deployment": {"latency_p95_ms": 26361.36, "cost_per_success": None},
            "release_gate": {"status": "BLOCKED_SAFETY"},
            "failure_fingerprint": {"n_failures": 20, "failure_rate": 0.526, "top_investigation_priority": "P0"},
        }],
        "comparisons": [{"baseline_run": "run-1", "candidate_run": "run-2", "quality_delta": 0.02,
                         "ci_low": -0.01, "ci_high": 0.05, "effect_size": 0.1, "status": "OBSERVED",
                         "practically_meaningful": False}],
        "robust_capability_score": {"mean_quality": 0.47, "configuration_variance": 0.0, "lambda": 1.0,
                                    "score": 0.47, "experimental": True},
        "pareto": {"pareto": {"frontier": ["run-1"], "dominated": [], "excluded": []}},
        "review": {"status": "NOT_PROVIDED", "human_reviewed": False, "n_annotations": 0},
        "deviations": {"status": "NOT_ASSESSED"},
        "limitations": ["No causal conclusions"],
    }


def test_redaction_keeps_decimal_metrics_but_still_removes_card_numbers():
    assert redact_text_for_report(f"Mean {LONG_DECIMAL}") == f"Mean {LONG_DECIMAL}"
    assert "[REDACTED:card_like]" not in redact_text_for_report("quality 0.4736842105263158 and 0.999999999999999")
    assert redact_text_for_report("card 4111 1111 1111 1111") == "card [REDACTED:card_like]"
    assert redact_text_for_report("mail person@example.com") == "mail [REDACTED:email]"


def test_run_html_renders_metrics_and_config_as_readable_html():
    html = render_run_html(_run_payload())
    assert "<table" in html and "class='card'" in html
    assert "[REDACTED:card_like]" not in html
    assert "0.4737" in html  # the measured mean survives redaction and formatting
    assert "unavailable" in html.lower()  # missing values are explicit
    assert "&#x27;" not in html  # no Python repr of mappings
    assert '{"currency": "USD", "input_per_million": null, "source": "manual_config"}' in html
    assert "<pre>#" not in html


def test_experiment_html_is_html_not_markdown():
    html = render_experiment_html(_experiment_result())
    assert "<table" in html and "Factor breakdown" in html
    assert "<pre>#" not in html and "- Cells:" not in html
    assert "0.4700" in html
    assert "sarvam_application_real_eval_v1" in html


def test_study_html_is_html_not_markdown():
    html = render_study_html(_study_summary())
    assert "<table" in html and "Runs and configurations" in html
    assert "<pre>#" not in html and "&gt;" not in html
    assert "<script>" not in html
    assert "BLOCKED_SAFETY" in html
    assert "26,361.36" in html  # large numbers are grouped for reading


def test_safety_html_is_html_not_markdown():
    payload = {
        "manifest": {"run_id": "safety-1", "evidence": {"mode": "LOCAL_REAL_MODEL"},
                     "entrypoint_command": "platform-safety"},
        "metrics": {
            "safety": {"n_cases": 11, "n_evaluated": 11, "attack_success_rate": 0.6,
                       "category_pass_rate": 0.4545, "weighted_risk_score": 1.1,
                       "by_category": {"jailbreak": {"n": 5, "passed": 2, "failed": 3,
                                                    "pass_rate": 0.4, "weighted_risk": 0.6}},
                       "by_severity": {}, "weighted_failures": []},
            "release_gate": {"status": "BLOCKED_SAFETY", "reasons": ["attack_success_rate=0.6 violates max 0.1"]},
        },
        "failures": [],
    }
    html = render_safety_html(payload)
    assert "<table" in html and "Attack success rate" in html
    assert "<pre>#" not in html
    assert "0.6000" in html
    assert "NOT PRODUCTION APPROVAL" in html
