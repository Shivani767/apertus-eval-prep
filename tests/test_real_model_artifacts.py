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

from build_real_model_notebooks import MODELS, TEMPLATE, render_notebook, serialise  # noqa: E402
from summarise_real_model_results import build_summary, render_markdown  # noqa: E402

CURATED = Path("results") / "colab_real_model" / "Qwen2.5-3B-Instruct"


def test_generated_notebooks_match_the_template():
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    for model in MODELS:
        path = ROOT / "notebooks" / model.notebook_name
        assert path.exists(), f"missing {model.notebook_name}; run scripts/build_real_model_notebooks.py"
        expected = serialise(render_notebook(template, model))
        assert path.read_text(encoding="utf-8") == expected, (
            f"{model.notebook_name} is stale; re-run scripts/build_real_model_notebooks.py"
        )


def test_generated_notebooks_pin_one_model_and_keep_no_outputs():
    for model in MODELS:
        notebook = json.loads((ROOT / "notebooks" / model.notebook_name).read_text(encoding="utf-8"))
        sources = "".join("".join(cell["source"]) for cell in notebook["cells"])
        assert f'MODEL_ID = "{model.model_id}"' in sources
        assert f"phase8_real_colab/{model.hf_name}" in sources
        assert f"apertus_phase8_real_colab_{model.hf_name}_export" in sources
        if model.model_id != "Qwen/Qwen2.5-3B-Instruct":
            assert "Qwen/Qwen2.5-3B-Instruct" not in sources, (
                f"{model.notebook_name} still references the template's baseline model"
            )
        for cell in notebook["cells"]:
            assert not cell.get("outputs"), f"{model.notebook_name} carries stored outputs"
            assert not cell.get("execution_count"), f"{model.notebook_name} carries an execution count"
            if cell["cell_type"] == "code":
                compile("".join(cell["source"]), model.notebook_name, "exec")


def test_curated_summary_matches_committed_runs(monkeypatch):
    monkeypatch.chdir(ROOT)
    summary_path = CURATED / "summary.json"
    assert summary_path.exists(), "run scripts/summarise_real_model_results.py for the curated results"
    committed = json.loads(summary_path.read_text(encoding="utf-8"))
    fresh = json.loads(json.dumps(build_summary(CURATED)))
    assert committed == fresh, "committed summary.json is stale or hand-edited"
    assert committed["totals"] == {
        "n_runs": 11,
        "n_real_runs": 10,
        "n_non_real_runs": 1,
        "n_scored_examples": 257,
    }
    assert committed["provenance"]["models"] == ["Qwen/Qwen2.5-3B-Instruct@main"]
    assert committed["by_suite"]["local_variance"]["n_runs"] == 6
    assert committed["by_suite"]["local_safety"]["gate_statuses"] == {"BLOCKED_SAFETY": 1}


def test_curated_summary_markdown_is_generated(monkeypatch):
    monkeypatch.chdir(ROOT)
    summary = build_summary(CURATED)
    assert (CURATED / "summary.md").read_text(encoding="utf-8") == render_markdown(summary)
