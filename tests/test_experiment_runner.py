"""Tests for experiment_runner and report_generation. Synthetic data only."""

import json
from pathlib import Path

import pytest

from apertus_eval_prep.experiment_runner import (
    Environment,
    ExperimentResult,
    ExperimentRun,
    capture_environment,
)
from apertus_eval_prep.report_generation import generate_research_report


def test_environment_to_dict():
    env = Environment(git_sha="abc123", git_dirty=False)
    d = env.to_dict()
    assert d["git_sha"] == "abc123"
    assert d["git_dirty"] is False
    assert "python_version" in d
    assert "platform" in d
    assert "utc" in d


def test_capture_environment_real_repo(tmp_path):
    # real repo root has .git
    env = capture_environment(Path(".").resolve())
    assert env.git_sha is not None
    assert isinstance(env.git_dirty, bool)


def test_experiment_result_fields():
    r = ExperimentResult(
        run_id="r1", config_hash="h1", model_id="m1",
        factor="control", factor_level="control",
        accuracy=0.75, n_items=100, path="results/x.json",
    )
    assert r.status == "ok"
    assert r.accuracy == 0.75


def test_experiment_run_to_dict():
    run = ExperimentRun(
        experiment_id="test-exp",
        config_snapshot={"profile": "t4"},
        environment={"git_sha": "abc"},
        results=[ExperimentResult("r1", "h1", "m1", "control", "control", 0.8, 100, "p1")],
        registry_path="results/registry.jsonl",
        output_dir="reports/experiments",
    )
    d = run.to_dict()
    assert d["experiment_id"] == "test-exp"
    assert len(d["results"]) == 1
    assert d["results"][0]["accuracy"] == 0.8


def test_generate_research_report_full():
    run = ExperimentRun(
        experiment_id="test-exp",
        config_snapshot={"profile": "t4"},
        environment={"git_sha": "abc123", "git_dirty": False,
                      "python_version": "3.11", "platform": "Linux/x86_64",
                      "utc": "2025-01-01T00:00:00"},
        results=[
            ExperimentResult("r1", "h1", "model/A", "control", "control", 0.8, 800, "p1"),
            ExperimentResult("r2", "h2", "model/B", "control", "control", 0.6, 800, "p2"),
        ],
        registry_path="results/registry.jsonl",
        output_dir="reports/experiments",
    )
    report = generate_research_report(run, repo_root=Path(".").resolve(), n_boot=100, seed=0)
    assert "# Research Report: test-exp" in report
    assert "[MEASURED]" in report
    assert "[DERIVED]" in report
    assert "model/A" in report
    assert "model/B" in report
    assert "0.8000" in report
    assert "Git SHA" in report
    assert "experiment run" in report


def test_generate_report_single_model_no_ranking():
    run = ExperimentRun(
        experiment_id="single",
        config_snapshot={},
        environment={"git_sha": "x", "python_version": "3.11", "platform": "Linux", "utc": "t"},
        results=[ExperimentResult("r1", "h1", "model/A", "control", "control", 0.5, 100, "p1")],
        registry_path="reg.jsonl",
        output_dir="out",
    )
    report = generate_research_report(run, repo_root=Path(".").resolve(), n_boot=50, seed=0)
    assert "model/A" in report
    # single model -> no ranking stability section computed
    assert "Kendall-tau" not in report or "could not compute" in report


def test_generate_report_empty_results():
    run = ExperimentRun(
        experiment_id="empty",
        config_snapshot={},
        environment={"git_sha": "x", "python_version": "3.11", "platform": "Linux", "utc": "t"},
        results=[],
        registry_path="reg.jsonl",
        output_dir="out",
    )
    report = generate_research_report(run, repo_root=Path(".").resolve(), n_boot=50, seed=0)
    assert "Cells measured: 0" in report or "0.0000" in report