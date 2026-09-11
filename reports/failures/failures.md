# Failure taxonomy report

Categories are mutually exclusive; rates are over all items in scope.
A zero count is a measured zero, not a missing value.

## Phi-int4

- items: 800, overall failure rate: 0.30125

| category | count | rate |
|---|---|---|
| runtime_error | 0 | 0.0000 |
| empty_output | 0 | 0.0000 |
| unparseable | 0 | 0.0000 |
| wrong_answer | 241 | 0.3013 |
| correct | 559 | 0.6987 |

| task | total | wrong_answer | unparseable | empty_output | runtime_error |
|---|---|---|---|---|---|
| arc_easy | 200 | 4 | 0 | 0 | 0 |
| gsm8k | 200 | 96 | 0 | 0 | 0 |
| hellaswag | 200 | 44 | 0 | 0 | 0 |
| mgsm | 200 | 97 | 0 | 0 | 0 |

## SmolLM2-hf

- items: 800, overall failure rate: 0.6025

| category | count | rate |
|---|---|---|
| runtime_error | 0 | 0.0000 |
| empty_output | 0 | 0.0000 |
| unparseable | 0 | 0.0000 |
| wrong_answer | 482 | 0.6025 |
| correct | 318 | 0.3975 |

| task | total | wrong_answer | unparseable | empty_output | runtime_error |
|---|---|---|---|---|---|
| arc_easy | 200 | 56 | 0 | 0 | 0 |
| gsm8k | 200 | 136 | 0 | 0 | 0 |
| hellaswag | 200 | 134 | 0 | 0 | 0 |
| mgsm | 200 | 156 | 0 | 0 | 0 |
