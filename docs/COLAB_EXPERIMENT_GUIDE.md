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
