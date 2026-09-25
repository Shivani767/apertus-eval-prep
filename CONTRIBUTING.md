# Contributing

## Development setup

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
PYTHONPATH=src .venv/bin/python -m pytest -q
```

The core test suite is offline, CPU-only, and must not require API keys, paid providers, GPUs, or network access. Keep synthetic fixtures explicitly labelled as mock/demo evidence.

## Design rules

- Preserve the legacy `eval`, `sweep`, `report`, and research commands unless a migration is documented.
- Add type hints and docstrings to public APIs.
- Validate configuration and external records at boundaries; count missing/failed examples rather than dropping them silently.
- Keep raw observations separate from derived scores and make retention explicit.
- Redact credentials and PII; never put secrets, personal paths, or provider prices in fixtures.
- Add a focused unit test for every new decision rule and an integration test for cross-module behavior.
- Prefer deterministic synthetic fixtures for CI. Document when a heuristic is not a human or benchmark result.

## Before opening a pull request

Run:

```bash
PYTHONPATH=src .venv/bin/python -m compileall -q src
PYTHONPATH=src .venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-run \
  --config configs/platform_smoke.yaml --out runs/local-smoke

PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-fingerprint \
  --run runs/local-smoke/run-id

# rebuild the review report from the same immutable artifact
PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-report \
  --run runs/local-smoke/run-id --format both
```

Review generated artifacts for secrets and ensure generated `runs/` output is not committed. Use `docs/INDUSTRY_UPGRADE_PLAN.md` for architecture and migration context.

## Phase 8 study/review contributions

Study and annotation changes must remain offline-safe and evidence-safe. Real-model configs use placeholders and cannot silently select a mock adapter; mock studies require an explicit `allow_mock` flag. Review packages contain sanitized templates only until reviewers complete them with valid rubric labels, anonymous reviewer hashes, timestamps, confidence, and linked evidence references. Agreement metrics are consistency diagnostics, not correctness or production-approval claims.

Before submitting a Phase 8 change, validate the study config and deterministic fixtures:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_phase8_study.py -q
PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-export-review \
  --run runs/local-smoke/run-id --out review_package.jsonl \
  --sample-size 10 --sampling-strategy stratified --study-id local-demo
PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-study-analyze \
  --study-config configs/studies/phase8_mock_study.yaml \
  --runs RUN_A RUN_B --out reports/phase8-study
```

Do not commit completed private annotations, reviewer identities, private datasets, generated runs, or secrets. Use `docs/PHASE8_STUDY_PROTOCOL.md`, `docs/HUMAN_REVIEW_PROTOCOL.md`, and `docs/PHASE8_EXECUTION_RUNBOOK.md` for the full workflow.
