# Sarvam application study runbook

This is a preparation/runbook for an optional, user-initiated real-model study. It does not download or execute a model automatically.

## Before execution

1. Complete the preregistration and create a private working copy of this directory.
2. Choose 2–3 candidate model IDs and pin model/tokenizer revisions when the source supports immutable revisions.
3. Declare whether execution is local or Google Colab and record assigned hardware only after it is observed.
4. Choose manual pricing inputs or leave prices unavailable; do not copy provider prices from memory.
5. Run offline preflight and confirm the working tree/commit SHA.

## Optional environment

```bash
python -m pip install -e '.[dev]'
python -m pip install -e '.[real-model]'
```

For the external-provider template, set the named environment variables privately:

```bash
export EXTERNAL_PROVIDER_BASE_URL='<user-supplied-endpoint>'
export EXTERNAL_PROVIDER_API_KEY='<user-supplied-secret>'
```

Do not print or commit the key. The config contains only the variable name.

## Execution order

1. Offline framework smoke:
   ```bash
   PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-run \
     --config configs/platform_smoke.yaml --out runs/sarvam-preflight-smoke
   ```
2. Real-model smoke (only after explicit confirmation):
   ```bash
   PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-run \
     --config YOUR_PRIVATE_LOCAL_BASELINE.yaml --out runs/sarvam-local-smoke
   ```
3. Variance matrix:
   ```bash
   PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-matrix \
     --config YOUR_PRIVATE_LOCAL_VARIANCE.yaml --out runs/sarvam-local-variance
   ```
4. RAG/agent matrix:
   ```bash
   PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-matrix \
     --config YOUR_PRIVATE_LOCAL_RAG_AGENT.yaml --out runs/sarvam-local-episodes
   ```
5. Sanitized safety suite:
   ```bash
   PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-safety \
     --config YOUR_PRIVATE_LOCAL_SAFETY.yaml --out runs/sarvam-local-safety
   ```
6. Ingest compatible completed runs:
   ```bash
   PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-ingest-runs \
     --runs RUN_A RUN_B RUN_C --out reports/sarvam/points.json
   ```
7. Apply the experimental constraints:
   ```bash
   PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-select \
     --points reports/sarvam/points.json \
     --constraints configs/studies/phase8_sarvam_application_study/selection_constraints.json \
     --out reports/sarvam/selection.json
   ```
8. Export a sanitized review package and ingest completed annotations if available:
   ```bash
   PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-export-review \
     --run RUN_A --dimensions correctness groundedness safe_behavior instruction_following \
     --sample-size 30 --sampling-strategy stratified --seed 7 \
     --study-id sarvam_application_real_eval_v1 --out reports/sarvam/review_package.jsonl
   PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-ingest-review \
     --input YOUR_COMPLETED_ANNOTATIONS.jsonl \
     --study-id sarvam_application_real_eval_v1 --out reports/sarvam/review_results.json
   ```
9. Analyze the study only from compatible completed artifacts:
   ```bash
   PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-study-analyze \
     --study-config YOUR_PRIVATE_STUDY_METADATA.yaml \
     --runs RUN_A RUN_B RUN_C --reviews reports/sarvam/review_results.json \
     --out reports/sarvam/study
   ```
10. Rebuild reports and inspect gate/failure fingerprints:
   ```bash
   PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-report \
     --run RUN_A --format both
   PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-fingerprint --run RUN_A
   ```

## Verification gates

- Stop if the model/tokenizer identity is not recorded.
- Stop if dataset/task/prompt/metric/evidence identities do not match.
- Stop if the run lacks a manifest, resolved config, metrics, confidence intervals, gate report, or failure fingerprint.
- Stop if the sample count is below the preregistered minimum.
- Stop and report `INCONCLUSIVE` if provenance, compatibility, sample-count, or artifact-integrity requirements fail.
- Do not use `--allow-incompatible` for the main reported study.

## Output and hygiene

Each run should contain `manifest.json`, `config.resolved.yaml`, `raw_outputs.jsonl`, `scored_examples.jsonl`, `metrics.json`, `confidence_intervals.json`, `failures.jsonl`, `failure_fingerprint.json`, `gate_report.json`, `report.md`, and `report.html` where applicable. Do not commit generated runs, caches, weights, private datasets, credentials, or unredacted review content. Preserve only selected non-sensitive artifacts after privacy and licensing review.
