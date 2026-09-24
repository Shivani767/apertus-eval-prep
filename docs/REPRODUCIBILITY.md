# Reproducibility

A reproducible run records enough information to explain its result:

- resolved YAML configuration and semantic config hash;
- dataset path, byte hash, filters, split, and example count;
- prompt protocol and template hash;
- model identifier/revision, adapter, backend, device, precision, quantization, and decoding;
- seed, conditions, UTC time, Python/platform/package metadata, and Git commit/dirty state;
- raw observations, derived scores, failures, metrics, reports, and gate decision.

Git metadata is best-effort: an unavailable Git executable or non-repository checkout is recorded as unavailable rather than failing the run. Run IDs combine a UTC timestamp, slug, and configuration fingerprint. Existing run directories raise an error instead of being overwritten.

## Minimal reproduction

```bash
PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-run \
  --config configs/platform_smoke.yaml --out runs/reproduction
```

## Rebuilding reports

```bash
PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-report \
  --run runs/reproduction/run-id --format both
PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-fingerprint \
  --run runs/reproduction/run-id
```

These commands consume the immutable run directory and do not rerun the model. `failure_fingerprint.json` is derived from `failures.jsonl`; it is not a second source of raw evidence. The report generator escapes model/output content and exposes missing evidence rather than converting it to zero.

For a candidate comparison, keep the dataset, task selection, prompt protocol, evaluator, and scoring conditions aligned; change only the intended factor. The comparison artifact reports aligned and missing IDs. Raw retention and PII redaction are explicit configuration choices, so reproduction does not imply that sensitive text should be published.
