# Benchmark comparison report

Auto-generated from scored run JSON. Generative exact-match unless noted.
Runs loaded: **3**.

## Multi-model comparison

| label | model | rank | overall acc | 95% CI |
|---|---|---:|---:|---|
| Mac-canary | `Qwen2.5-0.5B-Instruct` | 1.0 | 0.7143 | — |
| SmolLM2-control | `SmolLM2-1.7B-Instruct` | 2.0 | 0.3975 | [0.3642, 0.4318] |
| SmolLM2-int8 | `SmolLM2-1.7B-Instruct` | 2.0 | 0.4175 | [0.3838, 0.452] |

### Per-task accuracy

| label | arc_easy | gsm8k | hellaswag | mgsm | multilingual | template_canary |
|---|---|---|---|---|---|---|
| Mac-canary | 1.0 | 0.25 | None | None | 0.875 | 0.75 |
| SmolLM2-control | 0.72 | 0.32 | 0.33 | 0.22 | None | None |
| SmolLM2-int8 | 0.725 | 0.355 | 0.36 | 0.23 | None | None |

## Multilingual breakdown

_No language summaries in loaded runs._

## Thinking vs non-thinking

_Pair runs with `thinking_mode: true/false` on the same model._

## Prompt robustness (paraphrase)

_Run paraphrase_id OFAT cells (`orig`, `p1`, `p2`) to populate._

## Hallucination (fact verification F1)

_Include `hallucination` task in eval config._

## Safety and bias

_Include `safety_bias` task in eval config._

## Robustness (noisy prompts)

_Include `robustness` task in eval config._

## Quantization evaluation

| model | quant | fp16 acc | quant acc | Δ pp | fp16 tps | quant tps |
|---|---|---:|---:|---:|---:|---:|
| `SmolLM2-1.7B-Instruct` | int8 | 0.3975 | 0.4175 | 0.02 | 23.833 | 7.449 |

## Cost–performance

_Set `cost_per_1m_input_tokens` / `cost_per_1m_output_tokens` in YAML to estimate USD._
