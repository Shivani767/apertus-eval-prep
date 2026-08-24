# Paper-matrix run status

| | n |
|---|---:|
| T4 cells in YAML | 34 |
| `status=ok` in `registry_paper.jsonl` | **14** |
| Missing | **20** |

## Present (committed)

| model | factor | level | overall |
|---|---|---|---|
| SmolLM2 / Qwen-3B / Phi | control | control | 318 / 515 / 536 |
| SmolLM2 / Qwen-3B / Phi | prompt_id | concise, 5shot | see registry |
| SmolLM2 | quantization | int8 / int4 | 334 / 309 |
| Qwen-7B | quantization | int4 | 543 |
| SmolLM2 / Qwen-3B | backend | vllm | 336 / 534 |

## Colab jobs

| Notebook | Cell | Job | Status |
|---|---|---|---|
| `colab_stability.ipynb` | **13** | Qwen-3B quantization | RUN NOW |
| same | 14 | Phi quantization | next |
| same | **16–18** (after pull) | **seed** SmolLM2 / Qwen / Phi | ready to run |
| `colab_stability_backend.ipynb` | Phi sweep | Phi backend=vllm | RUN NOW on vacant GPU |

## Still missing

- backend vLLM: Phi
- quantization: Qwen-3B, Phi
- seed 1/2 × 3 models
- sampled T=0.7 × 9
