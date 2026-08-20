# apertus-eval-prep

Frozen-prompt evaluation and serving harness. Same items, same gold extractor, Hugging Face `generate` or vLLM, chat template as a first-class knob, scores and TTFT written to JSON.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Shivani767/apertus-eval-prep/blob/master/notebooks/colab_stability.ipynb)

**Run the paper matrix on Colab T4:** open the badge, Runtime → GPU → T4, Run all. The notebook sweeps [`configs/experiments/stability.yaml`](configs/experiments/stability.yaml) into `results/registry_paper.jsonl` (34 cells, 800 items). Re-run the sweep cell after a disconnect; finished hashes skip.

This is **not** IndicQuant, not InferLite, and not an Alps job. It is the smallest public object that maps onto the Apertus Evaluations work: *same chat template, same tokenizer, vLLM vs training-style generate, scores that do not silently drift, jobs that rerun.*

A second track asks an original question: **how stable are generative benchmark scores and rankings under prompt, seed, backend, and quantization changes?** That study is GPU-only (Colab T4/A10). Mac remains the 28-item smoke and template canary.

A clone on a laptop or Colab is enough. No NDA.

## What a stranger can verify in 10 minutes

```bash
git clone https://github.com/Shivani767/apertus-eval-prep
cd apertus-eval-prep
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
python -m apertus_eval_prep eval --config configs/smoke.yaml --out results/smoke.json
```

If `python -m venv` errors about a PATH separator, the folder path contains `:`. Clone or copy to `~/apertus-eval-prep` first.


Smoke downloads `Qwen/Qwen2.5-0.5B-Instruct` (~1 GB) and scores 4 items. That proves the pipeline, not the model.

Then open `results/smoke.json`: model id, git commit, hardware, `chat_template`, backend, per-item generations, accuracy, TTFT / p95.

## Commands that produce the artefact

Mac (Hugging Face generate; vLLM does not run on macOS):

```bash
# 1. Rendered prompts with special tokens visible
python -m apertus_eval_prep dump-prompts --config configs/default.yaml --out results/prompts_tokenizer.txt

# 2. Score with the tokenizer chat template
python -m apertus_eval_prep eval --config configs/default.yaml --out results/hf_tokenizer.json

# 3. Same model, template omitted (the silent train/serve bug)
python -m apertus_eval_prep eval --config configs/no_template.yaml --out results/hf_none.json

# 4. Same model, Llama-3 template on a Qwen checkpoint (mismatched serving)
python -m apertus_eval_prep eval --config configs/mismatched.yaml --out results/hf_mismatched.json

# 5. Diff
python -m apertus_eval_prep compare results/hf_tokenizer.json results/hf_none.json --out results/compare_template.md
python -m apertus_eval_prep compare results/hf_tokenizer.json results/hf_mismatched.json --out results/compare_mismatch.md
```

GPU / Colab (vLLM). Open [`notebooks/colab_vllm.ipynb`](notebooks/colab_vllm.ipynb) or:

```bash
pip install -e ".[gpu]"
python -m apertus_eval_prep eval --config configs/vllm.yaml --out results/vllm_tokenizer.json
python -m apertus_eval_prep compare results/hf_tokenizer.json results/vllm_tokenizer.json --out results/compare_backend.md
```

vLLM is given **already-rendered completion strings**. The engine is not allowed to apply a second chat template. That is how double-templating is avoided, and how a backend delta stays a backend delta.

## Ranking stability study (Colab GPU)

Mac cannot run bitsandbytes or vLLM. **Paper matrix (do this on T4):**

[Open `notebooks/colab_stability.ipynb` in Colab](https://colab.research.google.com/github/Shivani767/apertus-eval-prep/blob/master/notebooks/colab_stability.ipynb)

```bash
python -m apertus_eval_prep sweep --config configs/experiments/stability.yaml \
  --profile t4 --out-dir results/runs --registry results/registry_paper.jsonl
```

34 cells × 800 items. `--profile t4` skips 7B fp16/int8/vLLM. If Colab drops, run the same command again, or add `--only-model HuggingFaceTB/SmolLM2-1.7B-Instruct` (then 3B, Phi, 7B). Do not write into `results/registry.jsonl` (that file is the n=4 smoke).

Paper: [`paper/stability.md`](paper/stability.md).

```bash
# Dry-run the OFAT matrix without loading a model
python -m apertus_eval_prep sweep --config configs/experiments/stability.yaml \
  --profile t4 --dry-run --out-dir results/runs --registry results/registry_paper.jsonl
```

Official slices live in [`data/official/`](data/official/) (ARC-Easy, GSM8K, HellaSwag, MGSM, n=200, Hub revisions in `SOURCES.md`). Scoring is **generative exact-match**, not lm-eval loglikelihood. Every run JSON includes a Wilson 95% CI. The report adds McNemar vs control, Kendall $\tau_b$ on rankings, and CI-overlap ties.

Snapshot (once, then commit JSONL):

```bash
pip install -e ".[snapshot]"
python scripts/snapshot_benchmarks.py
```

## What this measures

| Task | n | Why it is here |
|---|---|---|
| `arc_easy` | 8 | English multiple choice (ARC-style). Apertus suites include ARC. |
| `gsm8k` | 8 | Verifiable math. swiss-ai evals note GSM8K-style generation can move between HF and vLLM. |
| `multilingual` | 8 | EN / DE / FR / HI, MGSM-style. DE/FR are Swiss official languages; HI is a language I actually work in. |
| `template_canary` | 4 | Format-locked letters. Built to drop if the template is missing or wrong. |

Slice is frozen in [`data/eval_set.jsonl`](data/eval_set.jsonl). It is not the full Apertus suite and not a model-card claim.

## Chat-template modes

| `chat_template` | What the backends receive |
|---|---|
| `tokenizer` | `tokenizer.apply_chat_template(..., add_generation_prompt=True)` |
| `none` | Raw user string. Instruct models are then scored as if they were base models. |
| `mismatched` | Llama-3 special tokens wrapped around a Qwen prompt. A realistic serving misconfiguration. |

Apertus 1.5 serving docs pass `--chat-template-content-format string` and, for thinking mode, `--default-chat-template-kwargs.enable_thinking`. This repo is the small version of that concern.

## Mapping onto the Evaluations job

| Job language (Apertus / swiss-ai evals) | This repo |
|---|---|
| `hf` vs `vllm` backends | `--backend hf` / `--backend vllm` |
| `--chat-template` / `--no-chat-template` | `chat_template: tokenizer \| none \| mismatched` |
| Generation scores can differ across backends | `compare` on `hf_tokenizer.json` vs `vllm_tokenizer.json` |
| Jobs that rerun | Frozen JSONL + YAML + git commit in the manifest |
| TTFT / serving | `latency.ttft_ms_p95`, `tokens_per_sec_mean` in the same JSON |

I have not run Slurm on Alps. This is the same job at smaller scale.

## What would make two numbers incomparable

Read [`notes/incomparability.md`](notes/incomparability.md). Short version: template, tokenizer, revision, backend, `max_new_tokens`, sampling, dtype, and hardware. `compare` prints which of those actually changed.

Measured runs are interpreted in [`notes/findings.md`](notes/findings.md): two experiments (template on MPS; backend on a T4), with controls and caveats.

## Layout

```
configs/          default, smoke, no_template, mismatched, vllm
configs/experiments/  stability.yaml OFAT matrix
configs/prompts/      default, concise, 5shot
data/eval_set.jsonl   28-item template canary
data/official/        frozen ARC / GSM8K / HellaSwag / MGSM
src/apertus_eval_prep/
  backends/hf.py      generate + bitsandbytes int8/int4 (CUDA)
  backends/vllm_backend.py
  sweep.py registry.py stats.py report.py
notebooks/colab_vllm.ipynb
notebooks/colab_stability.ipynb   ranking sweep on T4
paper/stability.md
results/registry.jsonl + results/runs/
```

## Honesty

- Mac smoke is `Qwen/Qwen2.5-0.5B-Instruct` on 28 items. Ranking numbers come from Colab T4/A10 and the official 200-item slices.
- Generative exact-match is not a model-card headline and not lm-eval.
- No Megatron, no NCCL, no GH200, no Alps.
- Do not invent GPU tables. Run the notebook, then commit JSON.

## License

Apache-2.0. Evaluation items: see [`data/README.md`](data/README.md).
