"""Guard the generated per-model Colab notebooks and the curated run summaries.

These tests are cheap and offline: they re-render each notebook from the shared
template and re-derive each summary from the committed run tree, so a hand-edited
number or a stale notebook fails CI instead of reaching the study report.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_real_model_notebooks import MODELS, TEMPLATE, cell_sources, has_stored_outputs, render_notebook  # noqa: E402
from compare_real_model_results import collect as collect_models  # noqa: E402
from compare_real_model_results import render_markdown as render_comparison  # noqa: E402
from summarise_real_model_results import build_summary, render_markdown  # noqa: E402

CURATED_ROOT = Path("results") / "colab_real_model"


def _curated_models() -> list[Path]:
    return sorted(path for path in CURATED_ROOT.iterdir() if path.is_dir() and (path / "summary.json").exists())


def test_generated_notebooks_match_the_template_sources():
    """Notebook code must come from the template; Colab runtime state is allowed.

    A notebook that Colab executed and saved back is deliberately exempt: the generator
    refuses to overwrite it, so its stored outputs are that run's record. The pinning test
    below still applies to it.
    """
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    executed = []
    for model in MODELS:
        path = ROOT / "notebooks" / model.notebook_name
        assert path.exists(), f"missing {model.notebook_name}; run scripts/build_real_model_notebooks.py"
        existing = json.loads(path.read_text(encoding="utf-8"))
        if has_stored_outputs(existing):
            executed.append(model.notebook_name)
            continue
        assert cell_sources(existing) == cell_sources(render_notebook(template, model)), (
            f"{model.notebook_name} code is stale; re-run scripts/build_real_model_notebooks.py"
        )
    print("executed in Colab, sources not compared:", executed)


def test_generated_notebooks_pin_one_model_and_compile():
    """Each notebook names its own model everywhere, never another model's."""
    for model in MODELS:
        notebook = json.loads((ROOT / "notebooks" / model.notebook_name).read_text(encoding="utf-8"))
        sources = "".join("".join(cell["source"]) for cell in notebook["cells"])
        outputs = json.dumps([cell.get("outputs") for cell in notebook["cells"]])
        assert f'MODEL_ID = "{model.model_id}"' in sources
        assert f"phase8_real_colab/{model.hf_name}" in sources
        assert f"apertus_phase8_real_colab_{model.hf_name}_export" in sources
        for other in MODELS:
            if other.model_id == model.model_id:
                continue
            if model.model_id.startswith(other.model_id) or other.model_id.startswith(model.model_id):
                continue  # Qwen2.5-3B is a prefix of Qwen2.5-3B-Instruct
            assert other.model_id not in sources, f"{model.notebook_name} names {other.model_id} in its code"
            assert other.model_id not in outputs, f"{model.notebook_name} stores {other.model_id} output"
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                compile("".join(cell["source"]), model.notebook_name, "exec")


def test_every_curated_model_summary_is_generated_and_current(monkeypatch):
    """Summaries are derived, never hand-edited, for every curated model."""
    monkeypatch.chdir(ROOT)
    models = _curated_models()
    assert len(models) >= 2, "expected curated results for more than one model"
    for directory in models:
        committed = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
        fresh = json.loads(json.dumps(build_summary(directory)))
        assert committed == fresh, f"{directory.name}/summary.json is stale or hand-edited"
        assert (directory / "summary.md").read_text(encoding="utf-8") == render_markdown(committed)


def test_curated_models_share_one_core_evaluation_identity(monkeypatch):
    """A cross-model comparison is only valid when dataset/task/metric identity match."""
    monkeypatch.chdir(ROOT)
    identities = set()
    for directory in _curated_models():
        summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
        identity = (summary.get("suite_identities") or {}).get("local_variance") or {}
        identities.add((
            tuple(identity.get("dataset_hashes") or []),
            tuple(identity.get("task_hashes") or []),
            tuple(identity.get("metric_definition_versions") or []),
        ))
    assert len(identities) == 1, f"curated models disagree on the core evaluation identity: {identities}"


def test_cross_model_comparison_is_generated_and_comparable(monkeypatch):
    monkeypatch.chdir(ROOT)
    payload = json.loads(json.dumps(collect_models(CURATED_ROOT)))
    committed = json.loads((CURATED_ROOT / "comparison.json").read_text(encoding="utf-8"))
    assert committed == payload, "comparison.json is stale or hand-edited"
    assert (CURATED_ROOT / "comparison.md").read_text(encoding="utf-8") == render_comparison(payload)
    assert len(payload["models"]) >= 2
    for suite, identity in payload["comparable_suite_identities"].items():
        for field, values in identity.items():
            assert len(values) == 1, f"{suite}.{field} differs across models: {values}"


def test_curated_runs_keep_the_protocol_shape(monkeypatch):
    """Whatever the models, the protocol shape must stay the same to be comparable."""
    monkeypatch.chdir(ROOT)
    for directory in _curated_models():
        summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
        totals = summary["totals"]
        assert totals["n_runs"] == totals["n_real_runs"] + totals["n_non_real_runs"], directory.name
        assert totals["n_real_runs"] >= 9, directory.name
        assert totals["n_non_real_runs"] == 1, f"{directory.name}: mock smoke must stay separate"
        assert summary["by_suite"]["local_variance"]["n_runs"] == 6, f"{directory.name}: expected 3 seeds x 2 templates"
        assert "LOCAL_REAL_MODEL" in summary["provenance"]["evidence_modes"], directory.name
        assert all(run.get("gate_status") for run in summary["runs"]), f"{directory.name}: run without a gate status"
