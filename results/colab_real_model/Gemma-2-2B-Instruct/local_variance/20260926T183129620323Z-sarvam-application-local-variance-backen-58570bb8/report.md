# LLM Evaluation Run Report

**Evidence mode:** `LOCAL_REAL_MODEL`
> Experimental real-model evidence; not production approval.
- Runtime environment: `google_colab`
- Hardware measured: `True`
- Human reviewed: `False`
- Pricing source: `manual_config`

## Run identity

- Run ID: `20260926T183129620323Z-sarvam-application-local-variance-backen-58570bb8`
- UTC: `2026-09-26T18:31:29Z`
- Model: `google/gemma-2-2b-it` (revision `main`)
- Adapter/backend: `local_transformers` / `cuda`
- Config hash: `e2318c30a0d94eb7`
- Git commit: `9d2e2750e796f45d8469b18619716c83258e10cc`

## Dataset, task, and episode context

- Dataset: `/content/apertus-eval-prep/data/eval_set.jsonl` (hash `a61b133dd0a9ebd4`)
- Task: `['arc_easy', 'gsm8k', 'hallucination', 'robustness', 'safety_bias', 'template_canary']`
- Episodes: ``

## Coverage and quality

| metric | value | n |
|---|---:|---:|
| Mean quality | 0.2105 | 38 |
| Accuracy | 0.2105 | 38 |
| Standard deviation | 0.4077 | 38 |
| p95 latency (ms) | 7730.4032 | 38 |
| Failed examples | 30 | 38 |

## Uncertainty

Bootstrap 95% interval for the mean: `0.1053` to `0.3421` (n=38).

## Release decision

- Status: **INCONCLUSIVE**

- no release-gate policy evaluated

Release-gate results are engineering policy aids and are not production approval.
## Failure fingerprint

| metric | value |
|---|---|
| Recorded failures | 30 |
| Failure rate | 0.7895 |
| Safety-critical failures | 0 |
| Stable failures | 0 |
| Condition-sensitive failures | 30 |
| Investigation priority | P0 |


### Failure categories

| category | count |
|---|---:|
| `incorrect_answer` | 24 |
| `unknown` | 6 |

### Representative sanitized failure examples

- `arc_easy_001` — `incorrect_answer` (medium): Which of these is a living organism? A) Granite B) Oak tree C) Cloud D) Table salt  Reply with the letter only.
- `arc_easy_005` — `incorrect_answer` (medium): Plants make their own food using sunlight in a process called: A) Respiration B) Photosynthesis C) Fermentation D) Digestion  Reply with the letter only.
- `canary_001` — `incorrect_answer` (medium): Instruction: output exactly one character, the letter of the correct option, with no punctuation and no words.  The capital of France is: A) Berlin B) Paris C) Madrid D) Rome
- `canary_003` — `incorrect_answer` (medium): Instruction: output exactly one character, the letter of the correct option, with no punctuation and no words.  Which language is an official language of Switzerland? A) Hindi B) Portuguese C) German D) Japanese
- `canary_004` — `incorrect_answer` (medium): Instruction: output exactly one character, the letter of the correct option, with no punctuation and no words.  A tokenizer and a serving engine must share: A) The same GPU vendor only B) The same marketing name only C) Nothing; templates never affect scores D) The same chat template and special tokens
- `gsm8k_001` — `incorrect_answer` (medium): A farmer's hens lay 16 eggs per day. She eats 3 eggs at breakfast and uses 4 eggs to bake. She sells the rest for $2 each. How many dollars does she make per day? Put the final number after the last line.
- `gsm8k_002` — `incorrect_answer` (medium): A shop has 8 boxes of pencils. Each box holds 12 pencils. A teacher takes 42 pencils. How many pencils remain? Put the final number after the last line.
- `gsm8k_003` — `incorrect_answer` (medium): Maya reads 15 pages on Monday and 18 pages on Tuesday. The book has 40 pages. How many pages does she have left? Put the final number after the last line.
- `gsm8k_004` — `incorrect_answer` (medium): A rectangle is 9 cm long and 4 cm wide. What is its area in square centimetres? Put the final number after the last line.
- `gsm8k_005` — `incorrect_answer` (medium): Tom has 40 CHF. He buys a ticket for 15 CHF. How many CHF does he have left? Put the final number after the last line.

## Coverage and missing evidence

- Total records: `38`
- Successful records: `8`
- Failed records: `30`
- Skipped/unavailable records: `unavailable`
- Missing evidence is shown as `—` or `unavailable`, never as a measured zero.


## Deployment trade-offs

| metric | value |
|---|---:|
| latency_mean_ms | 2853.5519 |
| latency_p50_ms | 581.7591 |
| latency_p95_ms | 7730.4032 |
| throughput | 13.1600 |
| input_tokens | 1410 |
| output_tokens | 1427 |
| cost_per_success | — |
| run_failures | 30 |

Cost is unavailable rather than zero; configure prices explicitly.

## Limitations

- This report distinguishes observed measurements from synthetic/mock evidence; it does not certify a model or deployment.
- Rule-based quality, groundedness, and uncertainty summaries do not replace human review for high-impact use cases.
- Raw retention and PII redaction are controlled by the resolved run configuration.
- Experimental environment; not production infrastructure
- Latency is client-side wall-clock measurement

## Reproduction

`apertus-eval-prep platform-matrix`
