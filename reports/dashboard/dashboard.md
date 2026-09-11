# Research dashboard

Registry: `results/registry_paper.jsonl` — 31 rows (MEASURED 25, SAMPLED 6, PENDING 0).

## Models (measured cells only)

| model | cells | mean acc | min | max |
|---|---|---|---|---|
| HuggingFaceTB/SmolLM2-1.7B-Instruct | 11 | 0.3745 | 0.2325 | 0.42 |
| Qwen/Qwen2.5-3B-Instruct | 11 | 0.6385 | 0.5125 | 0.6863 |
| Qwen/Qwen2.5-7B-Instruct | 1 | 0.6787 | 0.6787 | 0.6787 |
| microsoft/Phi-3.5-mini-instruct | 8 | 0.6506 | 0.5637 | 0.6987 |

## Evaluation Reliability Score (DERIVED, provisional)

- **ERS: 0.7155** (3 components)
- components: ci_separation=0.667, bootstrap_tau=0.829, config_stability=0.643, seed_stability=None
- bootstrap tau=0.8288888888888889, p(reversal)=0.25666666666666665
- missing cells skipped: 3

## Artifact verification (deviation checks)

- pass: **31** / fail: **0** (pending/no artifact: 0)

## Failure taxonomy (listed runs)

- **Phi-3.5-mini-instruct_quantization_int4_17c798b9a52bef83**: 800 items, failure rate 0.30125

