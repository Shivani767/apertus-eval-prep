# Score and ranking stability under evaluation configuration

**How stable are generative LLM benchmark scores and rankings when the prompt, seed, inference backend, or quantization changes?**

This note is the methodology for the study encoded in [`configs/experiments/stability.yaml`](../configs/experiments/stability.yaml). Tables below are produced by `python -m apertus_eval_prep paper-tables` from [`results/registry.jsonl`](../results/registry.jsonl). Until the Colab GPU sweep has been run, result tables are empty on purpose. Do not type numbers by hand.

## Abstract

Leaderboard numbers are often treated as properties of a model. They are also properties of an evaluation configuration: the prompt, the decoding seed, the serving engine, and the numeric precision. We freeze official slices of ARC-Easy, GSM8K, HellaSwag, and MGSM, score several instruction models with a generative exact-match protocol, and change **one configuration factor at a time**. We report Wilson 95% confidence intervals, McNemar tests on paired items, Kendall's $\tau_b$ on model rankings, and a CI-overlap rule that treats overlapping intervals as ties. The hypothesis is not that every knob moves accuracy — it is that **rank order can reverse even when interval estimates still overlap**.

## 1. Introduction

The existing canary in this repository already showed that omitting a chat template, or swapping Hugging Face `generate` for vLLM, moves accuracy on 28 frozen items ([`notes/findings.md`](../notes/findings.md)). That is a serving bug detector, not a ranking study.

This paper asks a broader question that evaluators actually need: **if you change a legitimate evaluation choice, do model A and model B keep their order?** A 3-point accuracy drop that leaves the ranking intact is a different claim from a 3-point drop that swaps first and second place.

We do not use lm-eval loglikelihood multiple choice. Every item is scored by generating text and extracting a letter or a number. That protocol is itself a configuration; we keep it fixed so the factors below stay interpretable.

## 2. Related work

Standard harnesses (lm-evaluation-harness, HELM, lighteval) pin prompts and metrics but still leave backend, quantization, and sampling as operator choices. swiss-ai evals-post-train notes that GSM8K-style generation can differ between Hugging Face and vLLM. Biderman et al. and related reproducibility work show that small prompt and seed changes move scores. This study's increment is **frozen official subsets + OFAT ranking + interval-aware ties**, in a cloneable YAML harness, with GPU runs on Colab rather than an internal cluster.

## 3. Method

### 3.1 Frozen slices

[`scripts/snapshot_benchmarks.py`](../scripts/snapshot_benchmarks.py) downloads Hub datasets at a recorded revision, shuffles with a documented seed, and writes JSONL. Eval never calls `datasets` at scoring time. Provenance: [`data/official/SOURCES.md`](../data/official/SOURCES.md).

| Task | Official source | n | Extractor |
|---|---|---|---|
| ARC-Easy | AI2 ARC Easy test | 200 | letter A–D |
| GSM8K | GSM8K test | 200 | last number |
| HellaSwag | HellaSwag validation | 200 | letter A–D (generative, not loglikelihood) |
| MGSM | MGSM EN/DE/FR | 200 | last number |

The original 28-item [`data/eval_set.jsonl`](../data/eval_set.jsonl) remains a Mac/template canary. It is not in the ranking table.

### 3.2 Models

GPU-first (Colab T4 or A10):

- `HuggingFaceTB/SmolLM2-1.7B-Instruct`
- `Qwen/Qwen2.5-3B-Instruct`
- `microsoft/Phi-3.5-mini-instruct`
- `Qwen/Qwen2.5-7B-Instruct` (int4 on T4; fp16 on A10)

Mac smoke stays `Qwen/Qwen2.5-0.5B-Instruct`. Ranking tables split an **fp16 cohort** (first three models) from an **int4 cohort** (all four) so size is not confounded with quantization.

### 3.3 Control and OFAT factors

Control: Hugging Face `generate`, tokenizer chat template, greedy (`temperature = 0`), `quantization: none`, prompt `default`, seed `0`.

One factor at a time ([`configs/experiments/stability.yaml`](../configs/experiments/stability.yaml)):

1. **Prompt:** `default` / `concise` / `5shot` ([`configs/prompts/`](../configs/prompts))
2. **Seed:** 0, 1, 2 at greedy decode, plus a sampled arm (`temperature = 0.7`)
3. **Backend:** `hf` vs `vllm` (vLLM gets already-rendered completion strings; no second chat template)
4. **Quantization:** `none` / `int8` / `int4` (bitsandbytes on HF only; not crossed with vLLM)

T4 skips 7B fp16, 7B int8, and 7B vLLM (`--profile t4`).

### 3.4 Statistics

For $k$ correct out of $n$, we report accuracy and a Wilson 95% interval. Paired configs on the same items use McNemar (continuity-corrected). Rankings use competition ranks on overall accuracy (average ranks on ties). Agreement with the control ranking is Kendall's $\tau_b$; we also count pairwise rank reversals. If two models' intervals overlap, we **report them as tied** even if the point estimates differ. That is the main reporting rule.

## 4. Setup

Clone, then on **Colab (Runtime → T4 GPU)** open [`notebooks/colab_stability.ipynb`](../notebooks/colab_stability.ipynb). The notebook installs `[gpu,viz]`, runs a short `--limit` demo, and can resume the full sweep through [`results/registry.jsonl`](../results/registry.jsonl). Mac is smoke-only; vLLM and bitsandbytes need CUDA.

```bash
python -m apertus_eval_prep sweep --config configs/experiments/stability.yaml \
  --out-dir results/runs --registry results/registry.jsonl --profile t4 --dry-run
python -m apertus_eval_prep report --registry results/registry.jsonl --out reports/stability
python -m apertus_eval_prep paper-tables --registry results/registry.jsonl --out paper/_generated_tables.md
```

## 5. Results

Insert generated tables (do not edit by hand):

```
python -m apertus_eval_prep paper-tables --out paper/_generated_tables.md
```

See [`paper/_generated_tables.md`](_generated_tables.md). Figures: `reports/stability/forest_control.png`, `kendall_tau.png`, `rank_heatmap.png`.

**Sanity check (not a ranking).** On the 28-item canary, `Qwen/Qwen2.5-0.5B-Instruct`, Mac MPS, greedy HF: tokenizer template 20/28 (71.4%), template omitted 15/28 (53.6%), Llama-3 wrap 12/28 (42.9%). On Colab T4, vLLM vs HF moved overall 20/28 → 18/28, concentrated on multilingual items. Those deltas justify treating backend and template as first-class factors. They are too small-$n$ to rank models.

**Colab smoke (first GPU registry, not the paper matrix).** `stability_smoke.yaml`, Tesla T4, 4 items, one 0.5B model, four OFAT cells. Control 1/4 with Wilson 95% CI **[0.046, 0.699]**. Kendall $\tau_b$ is undefined with one model. That width is the demo: $n=4$ cannot rank anything. See [`notes/findings.md`](../notes/findings.md) Experiment 3 and [`results/registry.jsonl`](../results/registry.jsonl).

## 6. Limitations

- Colab T4/A10, not Alps. 7B fp16 is A10-only.
- $n = 200$ per task. Wilson intervals will often overlap; that is data, not a failure.
- Generative HellaSwag/ARC is not the official loglikelihood protocol. Do not quote these numbers against lm-eval leaderboards.
- OFAT does not estimate interactions (except the explicit sampled-seed arm).
- Greedy seeds may not move greedy CUDA kernels. The sampled arm is the seed effect we actually interpret.

## 7. Conclusion

The artefact is the YAML matrix, the frozen JSONL, the registry, and the interval-aware ranking report. After the Colab sweep, the empirical claims to fill in are: which factor moves accuracy the most, which factor reverses ranks, and which reversals disappear once overlapping CIs are treated as ties.

Until the paper matrix is run, the measured claims are the 28-item template/backend canary and the $n=4$ T4 smoke (pipeline + wide CIs), not a model ranking.
