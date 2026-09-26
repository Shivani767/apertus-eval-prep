# LLM Evaluation Run Report

**Evidence mode:** `LOCAL_REAL_MODEL`
> Experimental real-model evidence; not production approval.
- Runtime environment: `google_colab`
- Hardware measured: `True`
- Human reviewed: `False`
- Pricing source: `manual_config`

## Run identity

- Run ID: `20260926T175602446851Z-sarvam-application-local-variance-baseli-e2813aec`
- UTC: `2026-09-26T17:56:04Z`
- Model: `google/gemma-2-2b-it` (revision `main`)
- Adapter/backend: `local_transformers` / `cuda`
- Config hash: `ba20283c3ee4f28a`
- Git commit: `0cafa9e38410358ed6186d620be2ba9509dab9b6`

## Dataset, task, and episode context

- Dataset: `/content/apertus-eval-prep/data/eval_set.jsonl` (hash `a61b133dd0a9ebd4`)
- Task: `['arc_easy', 'gsm8k', 'hallucination', 'robustness', 'safety_bias', 'template_canary']`
- Episodes: ``

## Coverage and quality

| metric | value | n |
|---|---:|---:|
| Mean quality | — | 0 |
| Accuracy | — | 0 |
| Standard deviation | — | 0 |
| p95 latency (ms) | — | 0 |
| Failed examples | 38 | 38 |

## Uncertainty

Bootstrap 95% interval for the mean: `—` to `—` (n=0).

## Release decision

- Status: **INCONCLUSIVE**

- no release-gate policy evaluated

Release-gate results are engineering policy aids and are not production approval.
## Failure fingerprint

| metric | value |
|---|---|
| Recorded failures | 38 |
| Failure rate | 1.0000 |
| Safety-critical failures | 0 |
| Stable failures | 0 |
| Condition-sensitive failures | 38 |
| Investigation priority | P0 |


### Failure categories

| category | count |
|---|---:|
| `infrastructure_error` | 38 |

### Representative sanitized failure examples

- `arc_easy_001` — `infrastructure_error` (medium): Which of these is a living organism? A) Granite B) Oak tree C) Cloud D) Table salt  Reply with the letter only.
- `arc_easy_002` — `infrastructure_error` (medium): What is the primary function of the human heart? A) Digest food B) Filter blood of urea C) Pump blood through the body D) Produce hormones for growth  Reply with the letter only.
- `arc_easy_003` — `infrastructure_error` (medium): Water boils at 100 degrees Celsius at standard atmospheric pressure. What state does it become? A) Gas (steam) B) Solid (ice) C) Plasma D) It remains liquid  Reply with the letter only.
- `arc_easy_004` — `infrastructure_error` (medium): Which force pulls objects toward the centre of the Earth? A) Magnetism B) Friction C) Tension D) Gravity  Reply with the letter only.
- `arc_easy_005` — `infrastructure_error` (medium): Plants make their own food using sunlight in a process called: A) Respiration B) Photosynthesis C) Fermentation D) Digestion  Reply with the letter only.
- `arc_easy_006` — `infrastructure_error` (medium): Which planet is closest to the Sun? A) Mercury B) Venus C) Earth D) Mars  Reply with the letter only.
- `arc_easy_007` — `infrastructure_error` (medium): Ice melting into water is an example of a: A) Chemical change that forms a new substance B) Nuclear change C) Physical change of state D) Biological mutation  Reply with the letter only.
- `arc_easy_008` — `infrastructure_error` (medium): Which organ of the human body is primarily responsible for exchanging oxygen and carbon dioxide? A) Liver B) Lungs C) Stomach D) Kidneys  Reply with the letter only.
- `canary_001` — `infrastructure_error` (medium): Instruction: output exactly one character, the letter of the correct option, with no punctuation and no words.  The capital of France is: A) Berlin B) Paris C) Madrid D) Rome
- `canary_002` — `infrastructure_error` (medium): Instruction: output exactly one character, the letter of the correct option, with no punctuation and no words.  2 + 2 equals: A) 4 B) 22 C) 5 D) 8

## Coverage and missing evidence

- Total records: `38`
- Successful records: `0`
- Failed records: `38`
- Skipped/unavailable records: `unavailable`
- Missing evidence is shown as `—` or `unavailable`, never as a measured zero.


## Deployment trade-offs

| metric | value |
|---|---:|
| latency_mean_ms | — |
| latency_p50_ms | — |
| latency_p95_ms | — |
| throughput | — |
| input_tokens | 0 |
| output_tokens | 0 |
| cost_per_success | — |
| run_failures | 38 |

Cost is unavailable rather than zero; configure prices explicitly.

## Limitations

- This report distinguishes observed measurements from synthetic/mock evidence; it does not certify a model or deployment.
- Rule-based quality, groundedness, and uncertainty summaries do not replace human review for high-impact use cases.
- Raw retention and PII redaction are controlled by the resolved run configuration.
- Experimental environment; not production infrastructure
- Latency is client-side wall-clock measurement

## Reproduction

`apertus-eval-prep platform-matrix`
