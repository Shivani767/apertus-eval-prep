"""Generate one Colab real-model notebook per model from a single template.

Usage:
    python3 scripts/build_real_model_notebooks.py            # write notebooks/
    python3 scripts/build_real_model_notebooks.py --check    # fail if out of date

`notebooks/colab_real_model_evaluation.ipynb` is the reviewed template. Each generated
notebook `notebooks/real_model_<slug>.ipynb` is the same workflow with the model pinned
in three places: the header, the configuration cell, and the Drive mirror/export names
(so parallel Colab sessions on different models cannot overwrite each other). Generated
notebooks are reproducible: running this script twice changes nothing.

Add a model by appending one `ModelNotebook` entry to MODELS and re-running.
"""
from __future__ import annotations

import argparse
import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "notebooks" / "colab_real_model_evaluation.ipynb"
NOTEBOOK_DIR = ROOT / "notebooks"
RESULTS_DIR = "results/colab_real_model"

TEMPLATE_TITLE = "# Real-model evaluation in Google Colab"


@dataclass(frozen=True)
class ModelNotebook:
    """One open-weight model that gets its own Colab notebook."""

    slug: str  # notebook file name: notebooks/real_model_<slug>.ipynb
    hf_name: str  # HF repository name, used for the results and Drive directories
    model_id: str  # Hugging Face model id written into MODEL_ID
    revision: str  # default revision; pin a commit sha before a study run
    title: str  # human-readable model name shown in the notebook header
    family_glob: str  # family token used by the Hugging Face cache-inspection cell
    description: str
    params: str
    fp16_weights: str
    license: str
    role: str
    max_new_tokens: int = 128
    status: str = "planned"

    @property
    def notebook_name(self) -> str:
        return f"real_model_{self.slug}.ipynb"

    @property
    def results_path(self) -> str:
        return f"{RESULTS_DIR}/{self.hf_name}"


#: Every model evaluated by this study, in the order the T4 plan runs them.
MODELS: tuple[ModelNotebook, ...] = (
    ModelNotebook(
        slug="qwen2.5-3b-instruct",
        hf_name="Qwen2.5-3B-Instruct",
        model_id="Qwen/Qwen2.5-3B-Instruct",
        revision="main",
        title="Qwen2.5 3B Instruct",
        family_glob="Qwen",
        description="Instruction-tuned 3B Qwen2.5 model; the primary baseline for the study.",
        params="3B",
        fp16_weights="~6.0 GB",
        license="Apache-2.0",
        role="Primary baseline; first real-model run on a free T4.",
        status="results committed",
    ),
    ModelNotebook(
        slug="phi-3.5-mini-instruct",
        hf_name="Phi-3.5-mini-instruct",
        model_id="microsoft/Phi-3.5-mini-instruct",
        revision="main",
        title="Phi-3.5 mini Instruct",
        family_glob="Phi",
        description="Instruction-tuned 3.8B Phi model with a 128k context window and a different tokenizer family.",
        params="3.8B",
        fp16_weights="~7.6 GB",
        license="MIT",
        role="Cross-family contrast at a similar size class; stresses robustness claims.",
    ),
    ModelNotebook(
        slug="smollm2-1.7b-instruct",
        hf_name="SmolLM2-1.7B-Instruct",
        model_id="HuggingFaceTB/SmolLM2-1.7B-Instruct",
        revision="main",
        title="SmolLM2 1.7B Instruct",
        family_glob="SmolLM",
        description="Small English instruction-tuned model used as the cheap end-to-end anchor.",
        params="1.7B",
        fp16_weights="~3.4 GB",
        license="Apache-2.0",
        role="Fastest full pass; low-quality control for failure-mode coverage.",
    ),
    ModelNotebook(
        slug="qwen2.5-1.5b-instruct",
        hf_name="Qwen2.5-1.5B-Instruct",
        model_id="Qwen/Qwen2.5-1.5B-Instruct",
        revision="main",
        title="Qwen2.5 1.5B Instruct",
        family_glob="Qwen",
        description="Smaller sibling of the baseline with the same tokenizer, so the size effect is isolated.",
        params="1.5B",
        fp16_weights="~3.0 GB",
        license="Apache-2.0",
        role="Same-family size contrast against Qwen2.5 3B.",
    ),
    ModelNotebook(
        slug="gemma-2-2b-it",
        hf_name="gemma-2-2b-it",
        model_id="google/gemma-2-2b-it",
        revision="main",
        title="Gemma 2 2B IT",
        family_glob="gemma",
        description="Instruction-tuned 2.6B Gemma 2 model with broad language coverage, used for the India-context diagnostic.",
        params="2.6B",
        fp16_weights="~5.2 GB",
        license="Gemma Terms of Use (gated: accept the licence)",
        role="Optional India-context diagnostic slice only, never the English primary comparison.",
        status="gated: accept the licence and set HF_TOKEN in the Colab environment",
    ),
)


def _to_source(text: str) -> list[str]:
    """Notebook cells store source as a list of lines with trailing newlines."""
    return text.splitlines(keepends=True)


def header_markdown(model: ModelNotebook) -> str:
    """Build the model-specific header that replaces the template title line."""
    return "\n".join(
        [
            f"{TEMPLATE_TITLE} - {model.title}",
            "",
            f"**Model under test:** `{model.model_id}` (revision `{model.revision}`; pin a commit sha before a study run).",
            f"**Description:** {model.description}",
            f"**Parameters:** {model.params} | **fp16 weights:** {model.fp16_weights} | **Licence:** {model.license}",
            f"**Role in the study:** {model.role}",
            f"**Status:** {model.status}",
            "",
            f"**Where the results belong:** `{model.results_path}/`; curate and summarise them with",
            f"`python3 scripts/summarise_real_model_results.py {model.results_path}`.",
            "",
            "**Parallel sessions:** this notebook mirrors its artifacts to",
            f"`MyDrive/apertus_runs/phase8_real_colab/{model.hf_name}` and exports",
            f"`apertus_phase8_real_colab_{model.hf_name}_export.zip`, so runs of other models cannot overwrite them.",
            "",
        ]
    )


def cell_replacements(model: ModelNotebook) -> list[tuple[str, str]]:
    """Textual replacements that pin the template to one model, applied in order."""
    return [
        ('MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"', f'MODEL_ID = "{model.model_id}"'),
        ('MODEL_REVISION = "main"', f'MODEL_REVISION = "{model.revision}"'),
        ("MAX_NEW_TOKENS = 128", f"MAX_NEW_TOKENS = {model.max_new_tokens}"),
        (
            'DRIVE_MIRROR = Path("/content/drive/MyDrive/apertus_runs/phase8_real_colab")',
            'DRIVE_MIRROR = Path("/content/drive/MyDrive/apertus_runs/phase8_real_colab/%s")' % model.hf_name,
        ),
        (
            "apertus_phase8_real_colab_export",
            "apertus_phase8_real_colab_%s_export" % model.hf_name,
        ),
        ('print("\\nQwen-related cache directories:")', 'print("\\n%s-related cache directories:")' % model.family_glob),
        ('cache_root.glob("*Qwen*")', 'cache_root.glob("*%s*")' % model.family_glob),
        ("qwen_dirs", "model_dirs"),
        ('print("No Qwen cache directory found.")', 'print("No matching model cache directory found.")'),
    ]


def render_notebook(template: dict[str, Any], model: ModelNotebook) -> dict[str, Any]:
    """Return the template notebook specialised to one model (pristine, no outputs)."""
    notebook = copy.deepcopy(template)
    applied = {old: 0 for old, _ in cell_replacements(model)}
    header_done = False
    for cell in notebook["cells"]:
        source = "".join(cell["source"])
        if cell["cell_type"] == "markdown" and not header_done and source.startswith(TEMPLATE_TITLE):
            body = source.split("\n", 1)[1].lstrip("\n") if "\n" in source else ""
            cell["source"] = _to_source(header_markdown(model) + body)
            header_done = True
            continue
        if cell["cell_type"] == "code":
            for old, new in cell_replacements(model):
                if old in source:
                    applied[old] += 1
                    source = source.replace(old, new)
            cell["source"] = _to_source(source)
            cell["outputs"] = []
            cell["execution_count"] = None
    missing = [old for old, count in applied.items() if count == 0]
    if missing:
        raise SystemExit(
            "%s: template no longer contains %s; update cell_replacements() before regenerating"
            % (model.notebook_name, missing)
        )
    if not header_done:
        raise SystemExit("%s: template header cell not found" % model.notebook_name)
    return notebook


def compile_check(notebook: dict[str, Any], name: str) -> int:
    """Compile every code cell; returns the number of code cells checked."""
    checked = 0
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        checked += 1
        try:
            compile("".join(cell["source"]), "%s cell %d" % (name, index), "exec")
        except SyntaxError as exc:
            raise SystemExit("%s cell %d: %s" % (name, index, exc)) from exc
    return checked


def serialise(notebook: dict[str, Any]) -> str:
    """Notebook JSON text in the format Colab and nbformat expect."""
    return json.dumps(notebook, indent=1, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="Verify notebooks are up to date instead of writing.")
    args = parser.parse_args()

    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    stale: list[str] = []
    for model in MODELS:
        notebook = render_notebook(template, model)
        code_cells = compile_check(notebook, model.notebook_name)
        text = serialise(notebook)
        target = NOTEBOOK_DIR / model.notebook_name
        existing = target.read_text(encoding="utf-8") if target.exists() else None
        if existing == text:
            print("up to date %s (%d code cells)" % (model.notebook_name, code_cells))
            continue
        stale.append(model.notebook_name)
        if args.check:
            continue
        target.write_text(text, encoding="utf-8")
        print("wrote %s (%d cells, %d code cells)" % (target.relative_to(ROOT), len(notebook["cells"]), code_cells))
    if args.check and stale:
        print("out of date (re-run without --check): %s" % ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
