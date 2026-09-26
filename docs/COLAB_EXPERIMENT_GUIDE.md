# Colab experiment guide

This guide covers optional open-weight local evaluation in Google Colab. It produces **experimental real-model evidence**, never a production benchmark or approval.

## Before starting

- Use a public model/dataset or approved private data outside the public repository.
- Never place Hugging Face tokens, API keys, passwords, or private dataset contents in a notebook or config.
- Prefer a pre-authenticated environment or Colab secret mechanism in a private workflow.
- Do not commit `runs/`, model caches, downloaded weights, or large generated reports.
- Start with the offline mock smoke command. If that fails, fix the framework before downloading a model.

## Setup and runtime inspection

Install the optional extra only in the Colab runtime:

```bash
python -m pip install -e '.[dev]'
python -m pip install -e '.[real-model]'
```

Inspect the environment:

```python
from apertus_eval_prep.utils.runtime_profile import profile_runtime
print(profile_runtime(device="auto", precision="auto", quantization="none"))
```

Colab is reported only when explicit Colab markers are available. CPU/CI fallback remains `local`. Missing Torch, CUDA, GPU, or memory facts are `None`/unavailable rather than fabricated.

## Configure a run

Edit one of:

- `configs/colab/local_real_model_smoke.yaml`
- `configs/colab/local_real_model_variance.yaml`
- `configs/colab/local_real_model_rag.yaml`
- `configs/colab/local_real_model_safety.yaml`

Replace `YOUR_MODEL_ID` and, where applicable, `OPTIONAL_PINNED_REVISION`. `trust_remote_code` defaults to false. Set device, dtype, quantization, seed, and optional manual prices only after understanding the recorded model/runtime conditions.

`notebooks/colab_real_model_evaluation.ipynb` provides a short setup, configuration, workflow, ingestion, selection, and export sequence.

## Per-model notebooks (one model per Colab session)

The reviewed notebook above is the shared template. Each model gets its own notebook,
generated from it so the workflow cannot drift between models:

```bash
python3 scripts/build_real_model_notebooks.py          # writes notebooks/real_model_<slug>.ipynb
python3 scripts/build_real_model_notebooks.py --check  # fails if a notebook is stale
```

The registry in `scripts/build_real_model_notebooks.py` records each model's id,
description, parameters, fp16 footprint, licence and role. Generation pins the model in
the notebook header, the configuration cell, the Drive mirror
(`MyDrive/apertus_runs/phase8_real_colab/<model>`) and the export file name
(`apertus_phase8_real_colab_<model>_export.zip`). Because those paths are model-specific,
several models can run in parallel in different Colab accounts without overwriting each
other's artifacts. Add a model by appending one `ModelNotebook` entry and re-running.

Curate a finished run into the repository and summarise it:

```bash
python3 scripts/summarise_real_model_results.py results/colab_real_model/<model>
```

`results/colab_real_model/<model>/summary.md` and `summary.json` are generated (never
hand-edited: a test regenerates them and compares) and record provenance — model
revision, git commit, dataset/task hashes — plus warnings for an unpinned revision,
identities that differ inside one suite, zero observed configuration variance, and
blocked gates. Only runs sharing `evidence_mode`, `dataset_hash`, `task_hash`,
`prompt_hash`, `prompt_version` and `metric_definition_version` are comparable;
`model_id` and its revision are expected to differ across models.

After a reporting change, rebuild the reports of curated models without a GPU or any
re-inference:

```bash
python3 scripts/regenerate_colab_reports.py results/colab_real_model/<model>
```

It rewrites every `report.md`/`report.html`, the safety report, the
`<experiment>.experiment.{md,html}` files and the study bundle from the stored
artifacts, so all models render in the same style.

After curating a second model, build the cross-model table (this also checks that the
core evaluation identity is identical across models):

```bash
python3 scripts/compare_real_model_results.py results/colab_real_model
```

It writes `results/colab_real_model/comparison.md` and `comparison.json`, and a test fails
if those files are stale, hand-edited, or if the curated models disagree on their
dataset, task or metric identity.

## Recommended order

1. Run `configs/platform_smoke.yaml`; this is synthetic `MOCK` framework validation.
2. Run the real-model smoke config on a tiny fixture.
3. Run the four-cell variance matrix (two seeds × two prompt templates).
4. Optionally run small RAG/agent and sanitized safety evaluations.
5. Ingest completed run directories with `platform-ingest-runs`.
6. Apply Phase 5 constraints with `platform-select`.
7. Rebuild `report.md` and `report.html` with `platform-report`.

Ingestion rejects mixed dataset/task/prompt/metric/evidence identities. Use `--allow-incompatible` only for an explicitly documented exploratory comparison; the output records every conflict.

## Colab limitations

- Hardware allocation can change between sessions and cannot be assumed stable.
- Sessions are ephemeral; download the selected artifacts before the session ends.
- Shared-infrastructure and notebook overhead affect wall-clock latency.
- Colab latency and optional cost estimates are not production-serving measurements.
- Model availability, download limits, and supported quantization can change.
- A Colab run is not a controlled hardware benchmark unless the protocol says so.
- High-impact safety claims require documented human review and approved testing.

## Export and hygiene

Download selected run directories and reports through Colab or user-owned Drive storage. Generated runs are git-ignored. Preserve a report externally or curate it into the repository only after checking evidence labels, privacy, licensing, secrets, and raw-content retention. Never commit model caches or credentials.
