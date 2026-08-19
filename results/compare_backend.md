# Eval comparison

- A: `results/hf_tokenizer_colab.json`
- B: `results/vllm_tokenizer.json`

## Settings that differ

| key | A | B |
|---|---|---|
| `backend` | hf | vllm |

## Accuracy

| task | acc A | acc B | delta (B−A) |
|---|---|---|---|
| arc_easy | 1.0 | 1.0 | 0.0 |
| gsm8k | 0.25 | 0.375 | 0.125 |
| multilingual | 0.875 | 0.5 | -0.375 |
| overall | 0.7143 | 0.6429 | -0.0714 |
| template_canary | 0.75 | 0.75 | 0.0 |

## Latency

- TTFT p95 (ms): A=192.63 B=None
- tokens/sec mean: A=17.327 B=None

If more than one setting changed, or hardware/dtype/backend all moved at once, do not treat the accuracy delta as a pure chat-template or pure-backend effect.

