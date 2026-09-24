# Benchmark comparison report

Auto-generated from scored run JSON. Generative exact-match unless noted.
Runs loaded: **1**.

## Multi-model comparison

| label | model | rank | overall acc | 95% CI |
|---|---|---:|---:|---|
| Mac-canary | `Qwen2.5-0.5B-Instruct` | 1.0 | 0.7143 | — |

### Per-task accuracy

| label | arc_easy | gsm8k | multilingual | template_canary |
|---|---|---|---|---|
| Mac-canary | 1.0 | 0.25 | 0.875 | 0.75 |

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

_Pair fp16 control with int8/int4 on the same model._

## Cost–performance

_Set `cost_per_1m_input_tokens` / `cost_per_1m_output_tokens` in YAML to estimate USD._
