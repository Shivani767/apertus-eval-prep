# apertus-eval-prep

Frozen-prompt evaluation and serving harness. Same items, same gold extractor, Hugging Face `generate` or vLLM, chat template as a first-class knob, scores and TTFT written to JSON.

This is **not** IndicQuant, not InferLite, and not an Alps job. It is the smallest public object that maps onto the Apertus Evaluations work: *same chat template, same tokenizer, vLLM vs training-style generate, scores that do not silently drift, jobs that rerun.*

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

## Layout

```
configs/          default, smoke, no_template, mismatched, vllm
data/eval_set.jsonl
src/apertus_eval_prep/
  backends/hf.py
  backends/vllm_backend.py   # optional extra: pip install -e ".[gpu]"
  templates.py               # one render path, both backends
  scoring.py
  run_eval.py
notebooks/colab_vllm.ipynb
results/          commit JSON after you run; do not type numbers by hand
```

## Honesty

- Model under test is `Qwen/Qwen2.5-0.5B-Instruct`, not `swiss-ai/Apertus-v1.5-8B`. Apertus 8B does not fit a Mac; the harness is the claim, not the 8B score.
- No Megatron, no NCCL, no GH200.
- Accuracy on 28 items is a regression canary, not a leaderboard.

## License

Apache-2.0. Evaluation items: see [`data/README.md`](data/README.md).
