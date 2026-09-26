# LLM Evaluation Run Report

**Evidence mode:** `LOCAL_REAL_MODEL`
> Experimental real-model evidence; not production approval.
- Runtime environment: `google_colab`
- Hardware measured: `True`
- Human reviewed: `False`
- Pricing source: `manual_config`

## Run identity

- Run ID: `20260926T125723102727Z-sarvam-application-local-variance-backen-16a89773`
- UTC: `2026-09-26T12:57:23Z`
- Model: `Qwen/Qwen2.5-1.5B-Instruct` (revision `main`)
- Adapter/backend: `local_transformers` / `cuda`
- Config hash: `14a4c6233790852e`
- Git commit: `a3179c6a0ed860344c1334721f1408437cf6b789`

## Dataset, task, and episode context

- Dataset: `/content/apertus-eval-prep/data/eval_set.jsonl` (hash `a61b133dd0a9ebd4`)
- Task: `['arc_easy', 'gsm8k', 'hallucination', 'robustness', 'safety_bias', 'template_canary']`
- Episodes: ``

## Coverage and quality

| metric | value | n |
|---|---:|---:|
| Mean quality | 0.0789 | 38 |
| Accuracy | 0.0789 | 38 |
| Standard deviation | 0.2697 | 38 |
| p95 latency (ms) | 9721.1049 | 38 |
| Failed examples | 35 | 38 |

## Uncertainty

Bootstrap 95% interval for the mean: `0.0000` to `0.1579` (n=38).

## Release decision

- Status: **INCONCLUSIVE**

- no release-gate policy evaluated

Release-gate results are engineering policy aids and are not production approval.
## Failure fingerprint

| metric | value |
|---|---|
| Recorded failures | 35 |
| Failure rate | 0.9211 |
| Safety-critical failures | 0 |
| Stable failures | 0 |
| Condition-sensitive failures | 35 |
| Investigation priority | P0 |


### Failure categories

| category | count |
|---|---:|
| `incorrect_answer` | 35 |

### Representative sanitized failure examples

- `arc_easy_002` — `incorrect_answer` (medium): What is the primary function of the human heart? A) Digest food B) Filter blood of urea C) Pump blood through the body D) Produce hormones for growth  Reply with the letter only.
- `arc_easy_003` — `incorrect_answer` (medium): Water boils at 100 degrees Celsius at standard atmospheric pressure. What state does it become? A) Gas (steam) B) Solid (ice) C) Plasma D) It remains liquid  Reply with the letter only.
- `arc_easy_004` — `incorrect_answer` (medium): Which force pulls objects toward the centre of the Earth? A) Magnetism B) Friction C) Tension D) Gravity  Reply with the letter only.
- `arc_easy_005` — `incorrect_answer` (medium): Plants make their own food using sunlight in a process called: A) Respiration B) Photosynthesis C) Fermentation D) Digestion  Reply with the letter only.
- `arc_easy_007` — `incorrect_answer` (medium): Ice melting into water is an example of a: A) Chemical change that forms a new substance B) Nuclear change C) Physical change of state D) Biological mutation  Reply with the letter only.
- `arc_easy_008` — `incorrect_answer` (medium): Which organ of the human body is primarily responsible for exchanging oxygen and carbon dioxide? A) Liver B) Lungs C) Stomach D) Kidneys  Reply with the letter only.
- `canary_001` — `incorrect_answer` (medium): Instruction: output exactly one character, the letter of the correct option, with no punctuation and no words.  The capital of France is: A) Berlin B) Paris C) Madrid D) Rome
- `canary_002` — `incorrect_answer` (medium): Instruction: output exactly one character, the letter of the correct option, with no punctuation and no words.  2 + 2 equals: A) 4 B) 22 C) 5 D) 8
- `canary_003` — `incorrect_answer` (medium): Instruction: output exactly one character, the letter of the correct option, with no punctuation and no words.  Which language is an official language of Switzerland? A) Hindi B) Portuguese C) German D) Japanese
- `canary_004` — `incorrect_answer` (medium): Instruction: output exactly one character, the letter of the correct option, with no punctuation and no words.  A tokenizer and a serving engine must share: A) The same GPU vendor only B) The same marketing name only C) Nothing; templates never affect scores D) The same chat template and special tokens

## Coverage and missing evidence

- Total records: `38`
- Successful records: `3`
- Failed records: `35`
- Skipped/unavailable records: `unavailable`
- Missing evidence is shown as `—` or `unavailable`, never as a measured zero.


## Deployment trade-offs

| metric | value |
|---|---:|
| latency_mean_ms | 4198.1069 |
| latency_p50_ms | 5056.6517 |
| latency_p95_ms | 9721.1049 |
| throughput | 18.4795 |
| input_tokens | 1365 |
| output_tokens | 2948 |
| cost_per_success | — |
| run_failures | 35 |

Cost is unavailable rather than zero; configure prices explicitly.

## Limitations

- This report distinguishes observed measurements from synthetic/mock evidence; it does not certify a model or deployment.
- Rule-based quality, groundedness, and uncertainty summaries do not replace human review for high-impact use cases.
- Raw retention and PII redaction are controlled by the resolved run configuration.
- Experimental environment; not production infrastructure
- Latency is client-side wall-clock measurement

## Reproduction

`apertus-eval-prep platform-matrix`
