# Ranking stability report

Generated from `results/registry.jsonl`. Numbers are generative exact-match,
not lm-eval loglikelihood. Wilson 95% CIs. Rank flips whose CIs overlap are ties.

Runs loaded: 12

## Control ranking

| rank | model | accuracy | 95% CI |
|---|---|---|---|
| 1.0 | `microsoft/Phi-3.5-mini-instruct` | 0.67 | [0.6367, 0.7017] |
| 2.0 | `Qwen/Qwen2.5-3B-Instruct` | 0.6438 | [0.61, 0.6762] |
| 3.0 | `HuggingFaceTB/SmolLM2-1.7B-Instruct` | 0.3975 | [0.3642, 0.4318] |

## Kendall tau vs control

| factor | level | tau-b | rank reversals | n models |
|---|---|---|---|---|
| control | control | 1.0 | 0 | 3 |
| prompt_id | 5shot | 0.3333 | 1 | 3 |
| prompt_id | concise | 1.0 | 0 | 3 |
| quantization | int4 | None | None | 2 |
| quantization | int8 | None | None | 1 |

## McNemar vs control (same items)

| model | factor | level | disagree | p |
|---|---|---|---|---|
| `HuggingFaceTB/SmolLM2-1.7B-Instruct` | prompt_id | concise | 0.32 | 0.0 |
| `Qwen/Qwen2.5-3B-Instruct` | prompt_id | concise | 0.2062 | 0.0 |
| `microsoft/Phi-3.5-mini-instruct` | prompt_id | concise | 0.2162 | 1e-06 |
| `HuggingFaceTB/SmolLM2-1.7B-Instruct` | prompt_id | 5shot | 0.2325 | 0.001616 |
| `Qwen/Qwen2.5-3B-Instruct` | prompt_id | 5shot | 0.16 | 0.003536 |
| `microsoft/Phi-3.5-mini-instruct` | prompt_id | 5shot | 0.3438 | 0.0 |
| `HuggingFaceTB/SmolLM2-1.7B-Instruct` | quantization | int4 | 0.2437 | 0.566718 |
| `HuggingFaceTB/SmolLM2-1.7B-Instruct` | quantization | int8 | 0.11 | 0.109819 |

## CI-overlap ties (control)

| model A | model B | point order | CI overlap (report as tie) |
|---|---|---|---|
| `HuggingFaceTB/SmolLM2-1.7B-Instruct` | `Qwen/Qwen2.5-3B-Instruct` | Qwen/Qwen2.5-3B-Instruct | False |
| `HuggingFaceTB/SmolLM2-1.7B-Instruct` | `microsoft/Phi-3.5-mini-instruct` | microsoft/Phi-3.5-mini-instruct | False |
| `Qwen/Qwen2.5-3B-Instruct` | `microsoft/Phi-3.5-mini-instruct` | microsoft/Phi-3.5-mini-instruct | True |
