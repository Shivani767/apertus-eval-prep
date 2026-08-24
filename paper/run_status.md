# Paper-matrix run status

Inventory of T4 cells from [`configs/experiments/stability.yaml`](../configs/experiments/stability.yaml) (`--profile t4`, 34 cells) against [`results/registry_paper.jsonl`](../results/registry_paper.jsonl).

**Do not invent rows.** A missing `config_hash` is missing. In-flight Colab jobs are not in this file until the run JSON is committed.

| | n |
|---|---:|
| T4 cells in YAML | 34 |
| `status=ok` in `registry_paper.jsonl` | **12** |
| Missing | **22** |

## Present (committed)

| model | factor | level | overall |
|---|---|---|---|
| SmolLM2-1.7B-Instruct | control | control | 318/800 |
| Qwen2.5-3B-Instruct | control | control | 515/800 |
| Phi-3.5-mini-instruct | control | control | 536/800 |
| SmolLM2-1.7B-Instruct | prompt_id | concise / 5shot | 186 / 274 |
| Qwen2.5-3B-Instruct | prompt_id | concise / 5shot | 410 / 549 |
| Phi-3.5-mini-instruct | prompt_id | concise / 5shot | 471 / 451 |
| SmolLM2-1.7B-Instruct | quantization | int8 / int4 | 334 / 309 |
| Qwen2.5-7B-Instruct | quantization | int4 | 543/800 |

## Colab jobs right now

| Notebook | Job | Status |
|---|---|---|
| [`colab_stability_backend.ipynb`](../notebooks/colab_stability_backend.ipynb) | Qwen-3B `backend=vllm` | **IN FLIGHT** — leave running |
| same | Phi `backend=vllm` | **Next vacant Colab** |
| same | SmolLM2 `backend=vllm` | Start only if not finished on Drive |
| [`colab_stability.ipynb`](../notebooks/colab_stability.ipynb) | Qwen-3B `quantization` | **Next vacant HF Colab** |
| same | Phi `quantization` | After Qwen-3B quant |

## Still missing

- backend vLLM: SmolLM2, Qwen-3B, Phi (until zips land)
- quantization: Qwen-3B int8/int4, Phi int8/int4
- seed 1/2 × 3 models; sampled T=0.7 × 9
