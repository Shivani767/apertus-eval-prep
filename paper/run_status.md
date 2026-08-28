# Paper-matrix run status

| | n |
|---|---:|
| T4 cells in YAML | 34 |
| `status=ok` in `registry_paper.jsonl` | **21** |
| Missing | **13** |

## Present (committed)

| model | factor | level | overall |
|---|---|---|---|
| SmolLM2 / Qwen-3B / Phi | control | control | 318 / 515 / 536 |
| SmolLM2 / Qwen-3B / Phi | prompt_id | concise, 5shot | see registry |
| SmolLM2 | quantization | int8 / int4 | 334 / 309 |
| Qwen-3B | quantization | int8 / int4 | **518 / 525** |
| Qwen-7B | quantization | int4 | 543 |
| SmolLM2 / Qwen-3B / Phi | backend | vllm | 336 / 534 / 537 |
| SmolLM2 / Qwen-3B | seed | 1 / 2 | 318 / 318; 515 / 515 (both match control) |

## Colab jobs

| Notebook | Job | Status |
|---|---|---|
| `colab_stability_backend.ipynb` | all 3 models `backend=vllm` | **DONE** |
| `colab_stability.ipynb` | SmolLM2 + Qwen-3B `seed` | **DONE** |
| same | Qwen-3B `quantization` int8 + int4 | **DONE** (from partial-3 zip) |
| same | Phi `seed` | RUN NEXT |
| same | Phi `quantization` | RUN NEXT |
| same | `sampled` | later |

## Still missing (13 cells)

- seed: Phi (1+2)
- quantization: Phi int8 + int4
- sampled T=0.7 × 9
