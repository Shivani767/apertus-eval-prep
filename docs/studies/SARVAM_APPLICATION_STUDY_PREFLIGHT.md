# Sarvam application study preflight

**Status:** preparation-only. No real model, GPU workload, model download, Colab runtime, external provider, or paid API was executed during preparation.

## Audited support

- `local_transformers`: optional lazy local/open-weight Transformers adapter.
- `openai_compatible`: explicit provider-neutral base URL plus environment-variable credential loading (`api_key_env`).
- `platform-run`, `platform-matrix`, `platform-episode`, `platform-safety`: existing run paths.
- `platform-ingest-runs`, `platform-select`, `platform-export-review`, `platform-ingest-review`, `platform-study-analyze`: existing ingestion, selection, review, and study-report paths.
- `real-model` extra: `torch`, `transformers`, and `accelerate`; optional and not required for mock CI.

## Offline preflight commands

Run from the repository root:

```bash
.venv/bin/python -m pytest -q --disable-warnings --maxfail=1
.venv/bin/python -m py_compile $(find src/apertus_eval_prep -type f -name '*.py' -print)
PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-run \
  --config configs/platform_smoke.yaml --out runs/preflight-smoke
PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-ingest-runs \
  --runs tests/fixtures/phase7_runs/real_a tests/fixtures/phase7_runs/real_b \
  --out reports/preflight-points.json
PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-select \
  --points reports/preflight-points.json \
  --constraints configs/studies/phase8_sarvam_application_study/selection_constraints.json \
  --out reports/preflight-selection.json
PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-study-analyze \
  --study-config configs/studies/phase8_mock_study.yaml \
  --runs tests/fixtures/phase7_runs/real_a tests/fixtures/phase7_runs/real_b \
  --out reports/preflight-study
git diff --check
```

The checked-in Phase 7 fixture directories intentionally omit `scored_examples.jsonl`. They validate ingestion and selection, but not paired study analysis. For an analyzer smoke only, copy them to `/tmp` and add deterministic synthetic rows marked as fixture-only; never use those rows as model or human evidence:

```bash
python - <<'PY'
import json, shutil
from pathlib import Path
src=Path('tests/fixtures/phase7_runs'); dst=Path('/tmp/sarvam-study-fixture')
shutil.rmtree(dst, ignore_errors=True); shutil.copytree(src, dst)
for name, score in [('real_a', 0.75), ('real_b', 1.0)]:
    rows=[{'example_id': f'fixture-{i}', 'score': score, 'correct': score >= 0.5} for i in range(1, 5)]
    (dst/name/'scored_examples.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
cfg={'study': {'study_id':'phase8-fixture-study', 'study_title':'Fixture-only preflight', 'research_question':'offline analyzer check', 'evidence_mode':'LOCAL_REAL_MODEL', 'matrix': {'models':['fixture/model-a','fixture/model-b'], 'prompt_templates':['v1'], 'seeds':[1], 'dtype':['float32'], 'quantization':['none']}}, 'base': {'adapter': {'kind':'local_transformers','model_id':'fixture/model-a','revision':'rev-a'}}, 'comparison': {'min_sample_size':2,'n_boot':40,'robust_capability_lambda':0.5}}
Path('/tmp/sarvam-study-fixture.yaml').write_text(json.dumps(cfg))
PY
PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-study-analyze \
  --study-config /tmp/sarvam-study-fixture.yaml \
  --runs /tmp/sarvam-study-fixture/real_a /tmp/sarvam-study-fixture/real_b \
  --out /tmp/sarvam-study-report
```

The generated fixture report must contain “No real-model evidence available”; it is a framework/analyzer smoke, not a study result.

The fixture-shaped study analysis is explicitly not real-model evidence and must produce the “No real-model evidence available” notice. The generated outputs are ignored or temporary and must not be treated as study results.

## Optional real-model environment

Only after explicit confirmation and in a user-controlled runtime:

```bash
python -m pip install -e '.[dev]'
python -m pip install -e '.[real-model]'
```

Optional provider variables, only if using the external template:

```bash
EXTERNAL_PROVIDER_BASE_URL
EXTERNAL_PROVIDER_API_KEY
```

Never put their values in config, notebooks, reports, terminal transcripts intended for archiving, or git.

## Expected outputs

Local runs: `runs/<run_id>/` with manifest, resolved config, raw/scored records, metrics, confidence intervals, failures/fingerprint, gate report, and reports. Study analysis: `reports/sarvam/study/` with JSON, Markdown, HTML, CSV, review summary, and limitations. Ingestion/selection outputs are JSON.

## Stop conditions

Stop and report `INCONCLUSIVE` if provenance is incomplete, identities are incompatible, samples are below the preregistered plan, or artifact integrity fails. Do not use `--allow-incompatible` for the main study.

## Limitations

Preflight validates configuration and harness behavior, not model quality, safety, hardware allocation, provider availability, or production latency. The study-specific configs intentionally contain placeholders and must be copied privately before any real execution.
