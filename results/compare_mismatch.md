# Eval comparison

- A: `results/hf_tokenizer.json`
- B: `results/hf_mismatched.json`

## Settings that differ

| key | A | B |
|---|---|---|
| `chat_template` | tokenizer | mismatched |

## Accuracy

| task | acc A | acc B | delta (B−A) |
|---|---|---|---|
| arc_easy | 1.0 | 0.5 | -0.5 |
| gsm8k | 0.25 | 0.25 | 0.0 |
| multilingual | 0.875 | 0.625 | -0.25 |
| overall | 0.7143 | 0.4286 | -0.2857 |
| template_canary | 0.75 | 0.25 | -0.5 |

## Latency

- TTFT p95 (ms): A=295.7 B=100.58
- tokens/sec mean: A=36.357 B=56.821

If more than one setting changed, or hardware/dtype/backend all moved at once, do not treat the accuracy delta as a pure chat-template or pure-backend effect.

