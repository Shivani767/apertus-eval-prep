# Phase 8 execution runbook

This runbook is for user-initiated experiments. It does not download or execute a model automatically.

1. Commit current changes and create a study branch.
2. Copy `configs/studies/phase8_real_model_study_template.yaml` to a private working config; complete `docs/PHASE8_PREREGISTRATION_TEMPLATE.md`.
3. Choose 2–3 model/configuration candidates.
4. Pin model and tokenizer revisions where possible.
5. Declare GPU/runtime and install the optional real-model extra only in the chosen environment.
6. Run offline smoke validation:
   ```bash
   PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-run --config configs/platform_smoke.yaml --out runs/smoke
   ```
7. Run warm-ups separately; do not include them in measured examples.
8. Run the study matrix:
   ```bash
   PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-matrix --config YOUR_STUDY_CONFIG --out runs/study
   ```
9. Run optional RAG/agent and sanitized safety suites using their configs.
10. Inspect manifests, metrics, gates, and failure fingerprints.
11. Export a review sample:
   ```bash
   PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-export-review --run runs/study/RUN_ID --dimensions correctness groundedness safe_behavior --sample-size 50 --sampling-strategy stratified --out review_package.jsonl
   ```
12. Collect annotations and ingest them:
   ```bash
   PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-ingest-review --input completed_annotations.jsonl --study-id YOUR_STUDY_ID --out review_results.json
   ```
13. Analyze the study:
   ```bash
   PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-study-analyze --study-config YOUR_STUDY_CONFIG --runs runs/study/RUN_A runs/study/RUN_B --reviews review_results.json --out reports/phase8_study
   ```
14. Review gates as engineering evidence only; they are not production approval.
15. Complete the technical report and portfolio case study without inventing findings.
16. Archive selected non-sensitive artifacts and record the exact commit SHA.

Never commit tokens, secrets, private datasets, downloaded weights, or large generated runs. Do not call Colab evidence a production benchmark.
