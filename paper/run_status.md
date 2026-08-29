# Paper-matrix run status

| | n |
|---|---:|
| T4 cells in YAML | 34 |
| `status=ok` in `registry_paper.jsonl` | **23** |
| Missing | **11** |

## Present (committed)

| model | factor | level | overall |
|---|---|---|---|
| SmolLM2 / Qwen-3B / Phi | control | control | 318 / 515 / 536 |
| SmolLM2 / Qwen-3B / Phi | prompt_id | concise, 5shot | see registry |
| SmolLM2 | quantization | int8 / int4 | 334 / 309 |
| Qwen-3B | quantization | int8 / int4 | 518 / 525 |
| Qwen-7B | quantization | int4 | 543 |
| SmolLM2 / Qwen-3B / Phi | backend | vllm | 336 / 534 / 537 |
| SmolLM2 / Qwen-3B / Phi | seed | 1 / 2 | 318 / 318; 515 / 515; **536 / 536** (all match control) |

## Colab jobs

| Notebook | Job | Status |
|---|---|---|
| `colab_stability_backend.ipynb` | all 3 models `backend=vllm` | **DONE** |
| `colab_stability.ipynb` | SmolLM2 + Qwen-3B + Phi `seed` | **DONE** (Phi from partial-4 zip) |
| same | Qwen-3B `quantization` int8 + int4 | **DONE** |
| same | Phi `quantization` | **RUN NOW** (partials on Drive: int8 ~773/800, int4 ~81/800) |
| same | `sampled` T=0.7 × 9 | later (cells 21–23) |

## Still missing (11 cells)

- quantization: Phi int8 + int4
- sampled T=0.7 × 9
