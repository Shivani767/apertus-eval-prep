# LLM Evaluation Run Report

**Evidence mode:** `LOCAL_REAL_MODEL`
> Experimental real-model evidence; not production approval.
- Runtime environment: `google_colab`
- Hardware measured: `True`
- Human reviewed: `False`
- Pricing source: `manual_config`

## Run identity

- Run ID: `20260926T131340933830Z-sarvam-application-local-user-baseline-8291f738`
- UTC: `2026-09-26T13:13:42Z`
- Model: `microsoft/Phi-3.5-mini-instruct` (revision `main`)
- Adapter/backend: `local_transformers` / `cuda`
- Config hash: `bfed0fe4fdeccab1`
- Git commit: `2ef3c0e27702e8a67fa46f7c582f79fadf05e9d5`

## Dataset, task, and episode context

- Dataset: `/content/apertus-eval-prep/data/eval_set.jsonl` (hash `a61b133dd0a9ebd4`)
- Task: `['arc_easy', 'gsm8k', 'hallucination', 'robustness', 'safety_bias', 'template_canary']`
- Episodes: ``

## Coverage and quality

| metric | value | n |
|---|---:|---:|
| Mean quality | 0.0000 | 4 |
| Accuracy | 0.0000 | 4 |
| Standard deviation | 0.0000 | 4 |
| p95 latency (ms) | 165381.1133 | 4 |
| Failed examples | 4 | 4 |

## Uncertainty

Bootstrap 95% interval for the mean: `0.0000` to `0.0000` (n=4).

## Release decision

- Status: **BLOCKED_QUALITY**

- attack_success_rate: insufficient evidence
- benign_false_refusal_rate: insufficient evidence
- high_severity_failures: insufficient evidence
- weighted_risk_score: insufficient evidence
- quality=0.0 violates min 0.75
- groundedness: insufficient evidence
- sample_size=4 violates min 20
- p95_latency_ms=165381.1132664498 violates max 5000.0
- failure_rate=1.0 violates max 0.2
- quality_ci_lower_bound=0.0 violates min 0.65

Release-gate results are engineering policy aids and are not production approval.
## Failure fingerprint

| metric | value |
|---|---|
| Recorded failures | 4 |
| Failure rate | 1.0000 |
| Safety-critical failures | 0 |
| Stable failures | 0 |
| Condition-sensitive failures | 4 |
| Investigation priority | P0 |


### Failure categories

| category | count |
|---|---:|
| `incorrect_answer` | 4 |

### Representative sanitized failure examples

- `arc_easy_001` — `incorrect_answer` (medium): Which of these is a living organism? A) Granite B) Oak tree C) Cloud D) Table salt  Reply with the letter only.
- `arc_easy_002` — `incorrect_answer` (medium): What is the primary function of the human heart? A) Digest food B) Filter blood of urea C) Pump blood through the body D) Produce hormones for growth  Reply with the letter only.
- `arc_easy_003` — `incorrect_answer` (medium): Water boils at 100 degrees Celsius at standard atmospheric pressure. What state does it become? A) Gas (steam) B) Solid (ice) C) Plasma D) It remains liquid  Reply with the letter only.
- `arc_easy_004` — `incorrect_answer` (medium): Which force pulls objects toward the centre of the Earth? A) Magnetism B) Friction C) Tension D) Gravity  Reply with the letter only.

## Coverage and missing evidence

- Total records: `4`
- Successful records: `0`
- Failed records: `4`
- Skipped/unavailable records: `unavailable`
- Missing evidence is shown as `—` or `unavailable`, never as a measured zero.


## Deployment trade-offs

| metric | value |
|---|---:|
| latency_mean_ms | 51587.0419 |
| latency_p50_ms | 5081.0301 |
| latency_p95_ms | 165381.1133 |
| throughput | 2.0160 |
| input_tokens | 192 |
| output_tokens | 416 |
| cost_per_success | — |
| run_failures | 4 |

Cost is unavailable rather than zero; configure prices explicitly.

## Limitations

- This report distinguishes observed measurements from synthetic/mock evidence; it does not certify a model or deployment.
- Rule-based quality, groundedness, and uncertainty summaries do not replace human review for high-impact use cases.
- Raw retention and PII redaction are controlled by the resolved run configuration.
- Experimental Colab environment; not production infrastructure
- Latency is client-side wall-clock measurement
- Results apply only to the recorded model revision and configuration

## Reproduction

`apertus-eval-prep platform-run`
