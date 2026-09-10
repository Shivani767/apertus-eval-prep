# Paper-matrix run status

| | n |
|---|---:|
| T4 cells in YAML | 34 |
| `status=ok` in `registry_paper.jsonl` | **31** |
| Missing | **3** |

## Present (committed)

| model | factor | level | overall |
|---|---|---|---|
| SmolLM2 / Qwen-3B / Phi | control | control | 318 / 515 / 536 |
| SmolLM2 / Qwen-3B / Phi | prompt_id | concise, 5shot | see registry |
| SmolLM2 | quantization | int8 / int4 | 334 / 309 |
| Qwen-3B | quantization | int8 / int4 | 518 / 525 |
| Phi | quantization | int8 / int4 | 538 / 559 |
| Qwen-7B | quantization | int4 | 543 |
| SmolLM2 / Qwen-3B / Phi | backend | vllm | 336 / 534 / 537 |
| SmolLM2 / Qwen-3B / Phi | seed | 1 / 2 | 318 / 318; 515 / 515; **536 / 536** (all match control) |
| SmolLM2 | sampled | t0.7_seed0 / t0.7_seed1 / t0.7_seed2 | 288 / 294 / 312 |
| Qwen-3B | sampled | t0.7_seed0 / t0.7_seed1 / t0.7_seed2 | 514 / 520 / 504 |

## Colab jobs

| Notebook | Job | Status |
|---|---|---|
| `colab_stability_backend.ipynb` | all 3 models `backend=vllm` | **DONE** |
| `colab_stability.ipynb` | SmolLM2 + Qwen-3B + Phi `seed` | **DONE** |
| same | Qwen-3B `quantization` int8 + int4 | **DONE** |
| same | Phi `quantization` int8 + int4 | **DONE** (merged: 538 / 559) |
| same | SmolLM2 + Qwen-3B `sampled` T=0.7 × 6 | **DONE** |
| same | Phi `sampled` T=0.7 × 3 | **RUN NOW** (only remaining cells) |

## Still missing (3 cells)

- sampled T=0.7: Phi t0.7_seed0 + t0.7_seed1 + t0.7_seed2
