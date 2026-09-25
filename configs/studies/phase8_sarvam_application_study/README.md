# Sarvam application study assets

This directory contains preparation-only assets for `sarvam_application_real_eval_v1`.

## Evidence boundary

- `study_metadata.yaml` is a real-study `StudySpec`; primary results require `LOCAL_REAL_MODEL` artifacts.
- `local_*.yaml` and `india_context_diagnostic.yaml` are runnable `RunSpec` templates with editable placeholders.
- `local_variance.yaml` and `local_rag_agent.yaml` are existing experiment-matrix configs.
- `external_provider_template.yaml` is a placeholder for an OpenAI-compatible provider; its key is read from `EXTERNAL_PROVIDER_API_KEY`.
- No credentials, model weights, real model IDs, or generated runs are stored here.
- The India-context dataset is a small exploratory diagnostic, not a multilingual benchmark and not part of the primary English result.

Copy this directory or the individual files into a private working location and replace `YOUR_MODEL_ID`, `OPTIONAL_PINNED_REVISION`, and any private runtime values. Keep the resulting private config out of git.

The execution order and stop conditions are in [RUNBOOK.md](RUNBOOK.md). Study claims must follow [SARVAM_APPLICATION_REAL_STUDY_PREREGISTRATION.md](../../docs/studies/SARVAM_APPLICATION_REAL_STUDY_PREREGISTRATION.md).

## Colab one-cell model selection

Open [notebooks/colab_real_model_evaluation.ipynb](../../../notebooks/colab_real_model_evaluation.ipynb) and edit only the marked selector cell:

```python
MODEL_ID = "YOUR_MODEL_ID"
MODEL_REVISION = "OPTIONAL_PINNED_REVISION"
TOKENIZER_ID = None
DEVICE = "cuda"
DTYPE = "float16"
QUANTIZATION = "none"
MAX_NEW_TOKENS = 256
TEMPERATURE = 0.0
TOP_P = 1.0
SEED = 11
```

Start with float16 and no quantization. Use int8/int4 only after the baseline succeeds and the optional quantization dependencies are installed. Do not enable `trust_remote_code` unless the model requires it and you have reviewed the code. If GPU memory is insufficient, choose a smaller model or lower `MAX_NEW_TOKENS`/batch size; do not silently change the recorded conditions. A safe private template is [local_user_config.example.yaml](local_user_config.example.yaml); copy it to `local_user_config.yaml` for private edits. The full checklist is [REAL_COLAB_EXECUTION_CHECKLIST.md](../../docs/studies/REAL_COLAB_EXECUTION_CHECKLIST.md).
