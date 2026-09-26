"""Replace the template's Hub auth cell with the tested package version.

The real-model notebooks are generated: `notebooks/colab_real_model_evaluation.ipynb`
is the reviewed source of truth and `scripts/build_real_model_notebooks.py`
propagates it. So this script edits the template, and the generator does the rest.
Pass ``--all`` only to fix generated files in place.

Idempotent: a cell already delegating to ``apertus_eval_prep.hub_auth`` is left
alone. Only the cell that defines ``authenticate_hugging_face`` is touched, and its
outputs are cleared because they belong to the old code.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "notebooks" / "colab_real_model_evaluation.ipynb"
NOTEBOOK_DIR = ROOT / "notebooks"

MARKER = "from apertus_eval_prep.hub_auth import"
DEFINITION = "def authenticate_hugging_face("
MODEL_ID_ASSIGNMENT = "MODEL_ID = "
#: Only these notebooks are expected to carry the cell; the stability and vLLM
#: notebooks run fixed public models and never had one.
REQUIRES_AUTH_CELL = "real_model_"


MARKDOWN_CELL = """## 0. Authenticate for gated models (only for gated repositories)

Most models in this study are public and need nothing here. Gated repositories — Google's Gemma
models, Meta's Llama models — additionally require a Hugging Face account that has **accepted the
model licence**, plus a token. A download that fails with `GatedRepoError` or
`401 Unauthorized` is an authentication problem, not a memory or configuration problem.

1. Sign in to the model page on huggingface.co (for example the Gemma or Llama repository you selected) with the account that
   will run the notebook and accept the licence. Acceptance is per account.
2. Create a read-only token at <https://huggingface.co/settings/tokens>.
3. In Colab, add it as a secret: the key icon in the left panel, new secret, key `HF_TOKEN`. Never
   paste a token into a notebook cell, a config file, or a commit.

The cell below authenticates from that secret, verifies the model is actually reachable, and prints
the commit SHA to use as `MODEL_REVISION`. The token is also exported into the environment, so the
`platform-*` subprocesses that actually download the weights can read it."""

NEW_CELL = '''# pyright: reportUndefinedVariable=false
from apertus_eval_prep.hub_auth import check_model_access as _check_model_access
from apertus_eval_prep.hub_auth import resolve_hub_token as _resolve_hub_token


def authenticate_hugging_face():
    """Resolve a token the Hub accepts, and hand it to the platform subprocess.

    Validated, not assumed: a revoked or expired token is rejected here instead
    of being reported as available, so a freshly rotated Colab secret is used
    instead of a stale cached one.
    """
    from apertus_eval_prep.hub_auth import ambient_token, colab_secret_token

    token, rejected = _resolve_hub_token(
        [("colab secret", colab_secret_token()), ("environment", ambient_token())]
    )
    if token:
        import os

        os.environ["HF_TOKEN"] = token
        print("Hugging Face: authenticated from an accepted token (not shown).")
    else:
        print("Hugging Face: no token the Hub accepts.")
        if rejected:
            print("Rejected token source(s):", ", ".join(rejected))
        print("Public models download anonymously; a gated one needs a fresh HF_TOKEN secret.")
    return token


def check_model_access(model_id=None):
    """Fail fast with instructions when the Hub will not serve the model.

    This proves the *download* works, not just the metadata: gated repositories
    publish their metadata to anonymous callers, so a metadata check alone passes
    and then every weight download fails with 401.
    """
    report = _check_model_access(model_id or MODEL_ID)
    print(report.summary())
    if report.is_gated:
        print("pin this revision for reproducibility: MODEL_REVISION =", report.revision)
    return report.revision


# Fail fast, before any GPU time is spent: this raises with the licence
# instructions if the Hub would refuse a weight download.
PINNED_REVISION = check_model_access()
'''


def _style(original: str) -> tuple[dict, bool] | None:
    """Detect the JSON formatting of an untouched notebook.

    Rewriting a notebook with different indentation turns a one-cell change into a
    ten-thousand-line diff that hides the actual edit. The parameters are found by
    round-tripping the file as it is, so the patch is written back in the style
    the notebook already uses. Returns the dumps kwargs and the trailing newline.
    """
    notebook = json.loads(original)
    for sort_keys in (False, True):
        for indent in (1, 2, 4):
            for ensure_ascii in (False, True):
                for trailing in ("\n", ""):
                    kwargs = {"indent": indent, "ensure_ascii": ensure_ascii, "sort_keys": sort_keys}
                    if json.dumps(notebook, **kwargs) + trailing == original:
                        return kwargs, trailing == "\n"
    return None


def _insert_auth_cell(notebook: dict) -> bool:
    """Add the missing cell pair directly after the cell that defines MODEL_ID.

    Two notebooks were overwritten by a Colab autosave of an older in-memory
    version, which silently removed their authentication cell. The insertion point
    is derived, not hard-coded: the cell must come after MODEL_ID, because the
    preflight at its end reads that variable.
    """
    cells = notebook.get("cells", [])
    for index, cell in enumerate(cells):
        if cell.get("cell_type") != "code" or MODEL_ID_ASSIGNMENT not in "".join(cell.get("source", [])):
            continue
        cells[index + 1 : index + 1] = [
            {"cell_type": "markdown", "metadata": {}, "source": MARKDOWN_CELL.splitlines(keepends=True)},
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": NEW_CELL.splitlines(keepends=True),
            },
        ]
        return True
    return False


def patch(notebook_path: Path) -> bool:
    original = notebook_path.read_text(encoding="utf-8")
    notebook = json.loads(original)
    changed = False
    for cell in notebook.get("cells", []):
        source = "".join(cell.get("source", []))
        if DEFINITION not in source or MARKER in source:
            continue
        cell["source"] = NEW_CELL.splitlines(keepends=True)
        cell["outputs"] = []
        cell["execution_count"] = None
        changed = True
    if not changed and notebook_path.name.startswith(REQUIRES_AUTH_CELL):
        changed = _insert_auth_cell(notebook)
    if not changed:
        return False
    style = _style(original)
    if style is None:
        raise SystemExit(
            f"{notebook_path.name}: unknown JSON formatting, refusing to rewrite it wholesale. "
            "Add this file's style to _style() so the diff stays reviewable."
        )
    kwargs, trailing_newline = style
    notebook_path.write_text(json.dumps(notebook, **kwargs) + ("\n" if trailing_newline else ""), encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--all",
        action="store_true",
        help="Patch every notebook instead of only the template (the generator propagates it).",
    )
    args = parser.parse_args()
    paths = sorted(NOTEBOOK_DIR.glob("*.ipynb")) if args.all else [TEMPLATE]
    for path in paths:
        print(("patched " if patch(path) else "skipped ") + path.name)



if __name__ == "__main__":
    main()
