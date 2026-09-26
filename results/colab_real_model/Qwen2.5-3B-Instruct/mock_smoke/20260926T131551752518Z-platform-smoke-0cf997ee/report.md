# LLM Evaluation Run Report

**Evidence mode:** `MOCK`
> Synthetic/mock evidence; not a real benchmark result.
- Runtime environment: `unavailable`
- Hardware measured: `False`
- Human reviewed: `False`
- Pricing source: `unavailable`

## Run identity

- Run ID: `20260926T131551752518Z-platform-smoke-0cf997ee`
- UTC: `2026-09-26T13:15:51Z`
- Model: `synthetic/mock-oracle-v1` (revision `fixture-v1`)
- Adapter/backend: `mock` / `cpu`
- Config hash: `92e89cf3eee68836`
- Git commit: `ab1473ecad6f7d1be6e1f7b82ee5fec414155664`

## Dataset, task, and episode context

- Dataset: `/content/apertus-eval-prep/data/platform_smoke.jsonl` (hash `34c6f7ab5f18a5b9`)
- Task: `['platform_qa']`
- Episodes: ``

## Coverage and quality

| metric | value | n |
|---|---:|---:|
| Mean quality | 1.0000 | 4 |
| Accuracy | 1.0000 | 4 |
| Standard deviation | 0.0000 | 4 |
| p95 latency (ms) | 49.9804 | 4 |
| Failed examples | 0 | 4 |

## Uncertainty

Bootstrap 95% interval for the mean: `1.0000` to `1.0000` (n=4).

## Release decision

- Status: **INCONCLUSIVE**

- no release-gate policy evaluated

Release-gate results are engineering policy aids and are not production approval.
## Failure fingerprint

| metric | value |
|---|---|
| Recorded failures | 0 |
| Failure rate | 0.0000 |
| Safety-critical failures | 0 |
| Stable failures | 0 |
| Condition-sensitive failures | 0 |
| Investigation priority | — |


### Failure categories

| category | count |
|---|---:|

### Representative sanitized failure examples

No representative failures were recorded; this is not evidence that no failures exist.

## Coverage and missing evidence

- Total records: `4`
- Successful records: `4`
- Failed records: `0`
- Skipped/unavailable records: `unavailable`
- Missing evidence is shown as `—` or `unavailable`, never as a measured zero.


## Deployment trade-offs

| metric | value |
|---|---:|
| latency_mean_ms | 43.4895 |
| latency_p50_ms | 43.2305 |
| latency_p95_ms | 49.9804 |
| throughput | 22.9941 |
| input_tokens | 110 |
| output_tokens | 4 |
| cost_per_success | — |
| run_failures | 0 |

Cost is unavailable rather than zero; configure prices explicitly.

## Limitations

- This report distinguishes observed measurements from synthetic/mock evidence; it does not certify a model or deployment.
- Rule-based quality, groundedness, and uncertainty summaries do not replace human review for high-impact use cases.
- Raw retention and PII redaction are controlled by the resolved run configuration.
- Synthetic evidence is not real model evidence.

## Reproduction

`apertus-eval-prep platform-run`
