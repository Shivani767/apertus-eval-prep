"""Notebooks must not reimplement Hub authentication.

The Gemma 2 2B run failed on all 257 examples while the notebook printed
"model access OK", because the auth cell validated nothing: it accepted an
ambient token without checking it, and treated public repository metadata as
proof of download access. The logic now lives in
``apertus_eval_prep.hub_auth``, which is unit tested, so the notebooks only
delegate to it. These tests keep them honest.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

NOTEBOOK_DIR = Path(__file__).resolve().parents[1] / "notebooks"
AUTH_DEFINITION = "def authenticate_hugging_face("
PACKAGE_IMPORT = "apertus_eval_prep.hub_auth"


def _notebooks_with_auth() -> list[Path]:
    found = []
    for path in sorted(NOTEBOOK_DIR.glob("*.ipynb")):
        notebook = json.loads(path.read_text(encoding="utf-8"))
        if any(AUTH_DEFINITION in "".join(c.get("source", [])) for c in notebook["cells"]):
            found.append(path)
    return found


def _auth_cell_source(path: Path) -> str:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    for cell in notebook["cells"]:
        source = "".join(cell.get("source", []))
        if AUTH_DEFINITION in source:
            return source
    raise AssertionError(f"{path.name} has no auth cell")


@pytest.mark.parametrize("path", _notebooks_with_auth(), ids=lambda p: p.name)
def test_auth_cell_delegates_to_the_tested_module(path: Path):
    source = _auth_cell_source(path)
    assert PACKAGE_IMPORT in source
    # Notebook-local token reading is the bug: it accepted a token it never checked.
    assert "from google.colab import userdata" not in source
    assert "already available" not in source


@pytest.mark.parametrize("path", _notebooks_with_auth(), ids=lambda p: p.name)
def test_the_preflight_still_runs_before_any_gpu_time(path: Path):
    """The cell must fail fast, not leave the check to a later, expensive cell."""
    assert "PINNED_REVISION = check_model_access()" in _auth_cell_source(path)


def test_every_real_model_notebook_has_an_auth_cell():
    names = {p.name for p in _notebooks_with_auth()}
    expected = {p.name for p in NOTEBOOK_DIR.glob("real_model_*.ipynb")}
    assert expected <= names, f"missing an auth cell: {sorted(expected - names)}"
