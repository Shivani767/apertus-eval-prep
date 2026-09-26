"""Notebooks must not reimplement Hub authentication.

The Gemma 2 2B run failed on all 257 examples while the notebook printed
"model access OK", because the auth cell validated nothing: it accepted an
ambient token without checking it, and treated public repository metadata as
proof of download access. The logic now lives in
``apertus_eval_prep.hub_auth``, which is unit tested, and the notebook template is
the single source of truth the generator propagates. These tests keep that true.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

NOTEBOOK_DIR = Path(__file__).resolve().parents[1] / "notebooks"
TEMPLATE = NOTEBOOK_DIR / "colab_real_model_evaluation.ipynb"
AUTH_DEFINITION = "def authenticate_hugging_face("
PACKAGE_IMPORT = "apertus_eval_prep.hub_auth"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _carries_colab_state(notebook: dict) -> bool:
    """True when Colab saved runtime state into the notebook.

    The generator deliberately leaves such a notebook alone: it is the record of a
    finished run. A frozen notebook is therefore exempt from the delegation check
    and picks the fix up the next time it is regenerated; its measured artifacts
    live in results/colab_real_model either way.
    """
    return any(cell.get("outputs") or cell.get("execution_count") for cell in notebook["cells"])


def _live_real_model_notebooks() -> list[Path]:
    live = []
    for path in sorted(NOTEBOOK_DIR.glob("real_model_*.ipynb")):
        if not _carries_colab_state(_load(path)):
            live.append(path)
    return live


def _auth_cell_source(notebook: dict) -> str:
    for cell in notebook["cells"]:
        source = "".join(cell.get("source", []))
        if AUTH_DEFINITION in source:
            return source
    raise AssertionError("no auth cell")


@pytest.mark.parametrize("path", [TEMPLATE, *_live_real_model_notebooks()], ids=lambda p: p.name)
def test_auth_cell_delegates_to_the_tested_module(path: Path):
    source = _auth_cell_source(_load(path))
    assert PACKAGE_IMPORT in source
    # Notebook-local token reading is the bug: it accepted a token it never checked.
    assert "from google.colab import userdata" not in source
    assert "already available" not in source


@pytest.mark.parametrize("path", [TEMPLATE, *_live_real_model_notebooks()], ids=lambda p: p.name)
def test_the_preflight_still_runs_before_any_gpu_time(path: Path):
    """The cell must fail fast, not leave the check to a later, expensive cell."""
    assert "PINNED_REVISION = check_model_access()" in _auth_cell_source(_load(path))


def test_the_template_carries_exactly_one_auth_cell():
    """One place to change, so the generated notebooks cannot drift apart again."""
    cells = [c for c in _load(TEMPLATE)["cells"] if AUTH_DEFINITION in "".join(c.get("source", []))]
    assert len(cells) == 1


def test_every_live_real_model_notebook_has_an_auth_cell():
    missing = [p.name for p in _live_real_model_notebooks() if AUTH_DEFINITION not in json.dumps(_load(p))]
    assert not missing, f"missing an auth cell: {missing}"
