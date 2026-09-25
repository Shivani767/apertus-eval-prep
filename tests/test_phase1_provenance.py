from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from apertus_eval_prep.adapters.base import CompletionRequest, ToolSpecView
from apertus_eval_prep.adapters.mock import MockAdapter
from apertus_eval_prep.core.artifacts import (
    FAILURES,
    MANIFEST,
    METRICS,
    RAW_OUTPUTS,
    RESOLVED_CONFIG,
    SCORED_EXAMPLES,
    RunStore,
)
from apertus_eval_prep.core.config import load_run_spec
from apertus_eval_prep.core.errors import AdapterError, AdapterTimeoutError, ArtifactError
from apertus_eval_prep.core.provenance import (
    build_dataset_lock,
    build_run_manifest,
)
from apertus_eval_prep.core.runner import run_evaluation
from apertus_eval_prep.utils.environment import git_metadata
from apertus_eval_prep.utils.hashing import (
    hash_bytes,
    hash_config,
    hash_dataset,
    hash_prompt,
    hash_task,
)
from apertus_eval_prep.utils.serialization import read_json, read_jsonl, read_yaml

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_contains_phase1_provenance(tmp_path):
    spec = load_run_spec(ROOT / "configs/platform_smoke.yaml")
    spec.prompt.prompt_id = "smoke-prompt"
    spec.prompt.version = "v1"
    dataset = build_dataset_lock(ROOT / "data/platform_smoke.jsonl", n_examples=4)
    manifest = build_run_manifest(
        spec,
        run_id="phase1-run",
        repo_root=ROOT,
        command="python -m apertus_eval_prep --token=secret123456",
        dataset_lock=dataset,
    )

    assert manifest["run_id"] == "phase1-run"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", manifest["utc"])
    assert manifest["model_id"] == spec.adapter.model_id
    assert manifest["model_revision"] == spec.adapter.revision
    assert manifest["dataset_id"] == dataset.id
    assert manifest["dataset_hash"] == dataset.hash
    assert manifest["task_id"]
    assert manifest["task_kind"] == "static_qa"
    assert manifest["task"]["kind"] == "static_qa"
    assert manifest["prompt"]["version"] == "v1"
    assert manifest["prompt"]["prompt_hash"] == manifest["prompt"]["template_hash"]
    assert manifest["config_hash"] == spec.config_hash()
    assert manifest["resolved_config_hash"] == manifest["config_hash"]
    assert manifest["seed"] == spec.decoding.seed
    assert manifest["backend"]["device"] == spec.runtime.device
    assert "secret123456" not in json.dumps(manifest)


def test_git_metadata_has_safe_fallback(monkeypatch, tmp_path):
    import apertus_eval_prep.utils.environment as environment

    monkeypatch.setattr(environment, "_git", lambda *args, **kwargs: None)
    metadata = git_metadata(tmp_path)
    assert metadata == {
        "available": False,
        "commit": None,
        "branch": None,
        "dirty": None,
        "dirty_files": None,
    }


def test_phase1_hash_helpers_are_stable_and_distinct(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"id":"x","prompt":"hello","gold":"world"}\n', encoding="utf-8")
    config = {"seed": 7, "model": {"id": "m", "revision": "r"}}
    same_config = {"model": {"revision": "r", "id": "m"}, "seed": 7}
    task = {"kind": "static_qa", "tasks": ["qa"], "limit": 4}
    assert hash_config(config) == hash_config(same_config)
    assert hash_prompt("same prompt") == hash_prompt("same prompt")
    assert hash_prompt("same prompt") != hash_prompt("different prompt")
    assert hash_dataset(dataset) == hash_bytes(dataset.read_bytes())
    assert hash_dataset(dataset) == hash_dataset(dataset)
    assert hash_task(task) == hash_task(dict(reversed(list(task.items()))))


def test_resolved_config_and_artifact_layout_are_written(tmp_path):
    spec = load_run_spec(ROOT / "configs/platform_smoke.yaml")
    result = run_evaluation(spec, ROOT, output_root=tmp_path, command="phase1-smoke")
    for name in (MANIFEST, RESOLVED_CONFIG, RAW_OUTPUTS, SCORED_EXAMPLES, METRICS, FAILURES, "report.md"):
        assert (result.directory / name).exists(), name
    resolved = read_yaml(result.directory / RESOLVED_CONFIG)
    assert resolved["adapter"]["kind"] == "mock"
    assert resolved["task"]["path"] == "data/platform_smoke.jsonl"
    assert resolved["prompt"]["version"] == "v1"
    assert resolved["decoding"]["seed"] == 7
    raw = read_jsonl(result.directory / RAW_OUTPUTS)
    scored = read_jsonl(result.directory / SCORED_EXAMPLES)
    assert len(raw) == len(scored) == 4
    assert "output_excerpt" not in scored[0]
    assert raw[0]["response"]["simulated"] is True


def test_mock_modes_cover_offline_behaviors():
    request = CompletionRequest(prompt="hello", example_id="x", seed=1)
    adapter = MockAdapter()
    first = adapter.complete(request)
    second = adapter.complete(request)
    different_seed = adapter.complete(CompletionRequest(prompt="hello", example_id="x", seed=2))
    assert first.text == second.text
    assert first.seed == 1
    assert first.variant == second.variant
    assert first.variant != different_seed.variant
    assert "[mock-variant:" in different_seed.text
    assert MockAdapter(mode="malformed").complete(request).text == "???"
    with pytest.raises(AdapterTimeoutError):
        MockAdapter(mode="timeout").complete(request)
    with pytest.raises(AdapterError):
        MockAdapter(mode="error").complete(request)
    tool_response = MockAdapter(mode="tool_call").complete(
        CompletionRequest(prompt="look up", example_id="x", tools=[ToolSpecView("lookup")])
    )
    assert tool_response.tool_calls[0].name == "lookup"


def test_run_store_writes_redacted_json_and_rejects_traversal(tmp_path):
    store = RunStore.create(tmp_path, run_name="phase1", config_hash="cfg", run_id="phase1-artifact")
    store.write_json("nested/value.json", {"api_key": "sk-abcdefghijklmnop", "ok": True})
    payload = read_json(store.directory / "nested/value.json")
    assert payload == {"api_key": "[REDACTED_FIELD]", "ok": True}
    with pytest.raises(ArtifactError):
        store.write_json("../outside.json", {})
