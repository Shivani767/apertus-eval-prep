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
