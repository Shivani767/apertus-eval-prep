# Paper-matrix run status

Inventory of T4 cells from [`configs/experiments/stability.yaml`](../configs/experiments/stability.yaml) (`--profile t4`, 34 cells) against [`results/registry_paper.jsonl`](../results/registry_paper.jsonl).

**Do not invent rows.** A missing `config_hash` is missing. In-flight Colab jobs are not in this file until the run JSON is committed.

| | n |
|---|---:|
| T4 cells in YAML | 34 |
| `status=ok` in `registry_paper.jsonl` | **5** |
| Missing | **29** |

Source hashes: `expand_ofat(..., profile="t4")` + `config_hash(comparable_settings())`.

## Present (committed JSON under `results/runs/`)

| model | factor | level | hash | overall |
|---|---|---|---|---|
| SmolLM2-1.7B-Instruct | control | control | `24ffe98d9250761d` | 318/800 |
| Qwen2.5-3B-Instruct | control | control | `cff017903a47abb9` | 515/800 |
| Phi-3.5-mini-instruct | control | control | `31791224954ba45c` | 536/800 |
| SmolLM2-1.7B-Instruct | prompt_id | concise | `a0852ca6fc3e5c08` | 186/800 |
| SmolLM2-1.7B-Instruct | prompt_id | 5shot | `b6968af4b73708f7` | 274/800 |

## Missing (TODO — no JSON, no number)

### prompt_id

- Qwen2.5-3B `concise` `e4980863069a102c`
- Qwen2.5-3B `5shot` `8b703d7cb8d9627a`
- Phi-3.5-mini `concise` `37963fc49f7e8eca`
- Phi-3.5-mini `5shot` `e8c0aa94458abbd2`

### seed (greedy 1, 2)

- SmolLM2 `1` `4ae7b5af354b3423`, `2` `5041b3a8bf44df73`
- Qwen2.5-3B `1` `e8b596c4b1a8a527`, `2` `02eb0dd059805c38`
- Phi-3.5-mini `1` `f6611690d3503f3e`, `2` `8e8f4b3cb10595a4`

### backend vLLM

- SmolLM2 `8b096c40a70ae947`
- Qwen2.5-3B `d504f107b78b6804`
- Phi-3.5-mini `e796a0ecee505133`

### quantization

- SmolLM2 int8 `46dd44d463433c26`, int4 `72ac0b51cec27817`
- Qwen2.5-3B int8 `6355a02b3f243353`, int4 `f9457562c8aec49f`
- Phi-3.5-mini int8 `cfd71ce6317d4a54`, int4 `17c798b9a52bef83`
- Qwen2.5-7B int4 `22a6a0a56a69a1cb` (only 7B cell on T4)

### sampled (T=0.7)

- SmolLM2 seeds 0/1/2: `9ab2746ead7e2cb9`, `b3a50eddee120ab8`, `9544473e05a6b577`
- Qwen2.5-3B: `5ca15230e22b3837`, `535c365ca69c6f1f`, `125dd27f9eac822d`
- Phi-3.5-mini: `3405cfac2bfc0fd2`, `14eb19d80de2f1c1`, `8de6d3f1716a5888`

## What cannot be computed yet

- Kendall $\tau_b$ on **ranking** under `prompt_id`: only SmolLM2 has prompt cells. Need ≥2 models at the same level.
- Any McNemar / $\tau_b$ for seed, backend, quantization, sampled: no paired JSON.
- `paraphrase_id` is in `stability.yaml` but **skipped on every profile** (official stems have no paraphrases). Use `configs/experiments/paraphrase.yaml` (n=4, not yet run). Not part of the 34 T4 cells.
- 7B int4 cohort ranking: no 7B row in the registry.
