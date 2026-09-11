# Evaluation Cost Tracking (Phase 10)

Research question this serves: **"How much evaluation is enough to make a
reliable model comparison?"** — the cost side of the cost-vs-confidence
trade-off.

## What the harness actually measures today

Per run (`results/runs/*.json` → `latency` block):

| Field | Meaning |
|---|---|
| `n` | number of scored model calls (items) |
| `ttft_ms_mean/p50/p95` | time to first token |
| `e2e_ms_mean/p95` | end-to-end latency per item |
| `tokens_per_sec_mean` | generation throughput |

`src/apertus_eval_prep/cost.py` extracts these into a `CostRecord` where
**every field carries an explicit quality label**:

- `MEASURED` — read from the artifact (positive finite number)
- `DERIVED` — `est_total_s = e2e_ms_mean * n / 1000` (estimated serial
  wall-clock; only exists where both inputs are measured)
- `UNAVAILABLE` — None / non-numeric / **0.0 placeholders** / negative

## Known data limitation (found by inspection, preserved not fixed)

The committed vLLM cell `Phi-3.5-mini-instruct_backend_vllm_e796a0ecee505133.json`
records `e2e_ms_mean: 0.0` and `ttft: None`. 0.0 ms for 800 model calls is a
backend placeholder, not a measurement. The cost model therefore labels those
fields UNAVAILABLE and keeps the raw value untouched — it never treats the
placeholder as zero cost, and never rewrites the artifact.

## What is intentionally absent

Monetary cost, GPU memory, and energy are not recorded anywhere by the
current harness, so they are not modeled. If a future backend records them,
they can be added as new fields with the same quality-label contract.

## Budget vs confidence

`budget_curve(observations)` validates and sorts caller-supplied
`(cost, confidence)` pairs (e.g. cumulative wall-clock vs the
`selecting_confidence` heuristic from Phase 9, recorded while replaying a
real run). **No real observation set exists yet** — the harness would need
one or more complete protocol families with per-run cost to produce one —
so no cost-vs-confidence figures or claims are made in this repo.
