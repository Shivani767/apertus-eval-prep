# Google Colab real-model execution checklist

Use this checklist for a user-initiated `LOCAL_REAL_MODEL` study. It is a preparation/verification aid, not production approval. Do not commit the notebook's credentials, private config, model weights, caches, private datasets, or unredacted outputs.

## Before the run

- [ ] Record the Git commit SHA in the run note and preregistration/deviation log.
- [ ] Complete the study preregistration and declare the task/model/runtime scope.
- [ ] Select one model ID; use a smaller model if GPU memory is limited.
- [ ] Pin model and tokenizer revisions where the source provides immutable revisions.
- [ ] Enable a GPU runtime in Colab and record the observed runtime profile.
- [ ] Review raw-output retention and PII redaction settings.
- [ ] Confirm no secrets, tokens, local paths, or private datasets are in the notebook/config.
- [ ] Run the offline mock smoke evaluation and confirm `evidence_mode: MOCK`.
- [ ] Confirm optional `real-model` dependencies are installed only in the intended environment.

## During the run

- [ ] Keep warm-up generation separate from measured examples.
- [ ] Save the generated runtime config and immutable run directory.
- [ ] Confirm the manifest says `LOCAL_REAL_MODEL` and `real_model_execution: true`.
- [ ] Confirm model/tokenizer/backend/device/dtype/quantization metadata is present.
- [ ] Keep errors and timeouts in the artifacts; do not silently retry them away.
- [ ] Preserve unavailable token counts and cost values as unavailable.

## After each run

- [ ] Check the Markdown/HTML evidence label and limitations.
- [ ] Inspect metrics, confidence intervals, deployment metrics, and failure fingerprints.
- [ ] Inspect tool traces and RAG/agent or safety metrics where applicable.
- [ ] Verify compatibility before ingesting runs for selection/study analysis.
- [ ] Run deployment selection without `--allow-incompatible`.
- [ ] Export a sanitized human-review package only after core English results are complete.
- [ ] Preserve only reviewed, non-sensitive artifacts for a portfolio case study.
- [ ] Complete the deviation log and record the exact reproduction command.
