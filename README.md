# apertus-eval-prep

**A public, frozen-prompt evaluation harness that treats serving configuration as part of the measurement, not as noise.**

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Shivani767/apertus-eval-prep/blob/master/notebooks/colab_stability.ipynb)

Author: [Shivani Bhandari](https://github.com/Shivani767) · Gurugram · [github.com/Shivani767/apertus-eval-prep](https://github.com/Shivani767/apertus-eval-prep)

This repository is the smallest object I can put on the public internet that maps onto the Apertus / Swiss AI Initiative **evaluations** problem: same items, same gold extractor, chat template as a first-class knob, Hugging Face `generate` vs vLLM on identical rendered strings, scores and TTFT in one JSON, jobs that rerun from git. It is **not** an Alps run, not `swiss-ai/Apertus-v1.5-8B`, and not a model card. It is the same *kind of job* at a scale a laptop and a Colab T4 can finish.

---

## Why this exists (the claim)

A leaderboard number is usually read as a property of a **model**. It is also a property of an **evaluation configuration**:

1. Which chat template wrapped the prompt (tokenizer vs none vs the wrong family’s special tokens).
2. Which engine decoded it (training-style `generate` vs a serving engine such as vLLM).
3. Which prompt wording, seed, and numeric precision were used.

If those knobs are not named, two labs can “evaluate the same model” and disagree without either being wrong. swiss-ai [evals-post-train](https://github.com/swiss-ai/evals-post-train) already warns that GSM8K-style **generation** can differ between Hugging Face and vLLM. Apertus serving docs pin `--chat-template-content-format string` for the same reason: the tokenizer and the engine must agree.

The working hypothesis of this repo is therefore not “my 0.5B model is good.” It is:

> **If the measurement pipeline is doing its job, changing the template or the backend must move the JSON in a way a stranger can replay. Rank order of models is a second question, and it needs intervals, not point estimates.**

That is the skill I want to take to an ETH / EPFL research-assistant or intern seat on open multilingual models: make incomparable numbers *look* incomparable, and make comparable numbers *stay* comparable.

---

## What is already measured (do not mix the tables)

Two experiments are finished and committed. Hardware is a confound: do not quote them as one knob.

### Experiment A — chat template (Mac, MPS, n=28 canary)

Same weights, same tokenizer, same items, greedy decode. Only `chat_template` changes. Probe model: `Qwen/Qwen2.5-0.5B-Instruct`.

| condition | overall | ARC | GSM8K | multilingual | canary |
|---|---|---|---|---|---|
| tokenizer (correct) | **20/28 (71.4%)** | 8/8 | 2/8 | 7/8 | 3/4 |
| none | **15/28 (53.6%)** | 5/8 | 2/8 | 5/8 | 3/4 |
| Llama-3 wrap on Qwen | **12/28 (42.9%)** | 4/8 | 2/8 | 5/8 | 1/4 |

**Reasoning.** GSM8K stayed 2/8 in all three runs: that is a capability floor on this probe, not a template effect. ARC and the format canary moved. The mismatched Llama-3 wrap is the realistic serving bug (engine default ≠ tokenizer template). Source: [`notes/findings.md`](notes/findings.md), [`results/compare_template.md`](results/compare_template.md).

### Experiment B — backend (Colab T4, template fixed)

Same rendered completion strings. vLLM is **not** allowed a second `llm.chat()` template. Only `backend` changes.

| backend | overall |
|---|---|
| Hugging Face `generate` | **20/28 (71.4%)** |
| vLLM | **18/28 (64.3%)**, −7.1 points |

The −7 points sit in multilingual (7/8 → 4/8), not in ARC. One extra GSM8K item flipped; on n=8 that is noise. **Do not read “vLLM is worse at math.”** Read: generative exact-match is backend-sensitive; compare models with a **fixed** backend. Source: [`results/compare_backend.md`](results/compare_backend.md).

### Experiment C — why n=4 is not a ranking (CI width)

Prefix Wilson intervals on already-scored items, no extra GPU jobs ([`reports/ci_width/ci_width.md`](reports/ci_width/ci_width.md)):

| run | n | acc | 95% Wilson CI | width |
|---|---:|---:|---|---:|
| T4 smoke control | 4 | 0.25 | [0.046, 0.699] | **0.654** |
| Mac canary (tokenizer) | 28 | 0.714 | [0.529, 0.848] | **0.318** |

A 25-point “win” on n=4 sits inside noise. That is the methodological point, not a model ranking.

### Experiment D — ranking matrix (in progress, official n=800)

Frozen Hub slices: ARC-Easy, GSM8K, HellaSwag, MGSM EN/DE/FR (200 each). Generative exact-match, Wilson 95% CI on every run. OFAT around a control (prompt, seed, backend, quantization). Method: [`paper/stability.md`](paper/stability.md).

Committed T4 **control** cells so far (greedy, tokenizer template, HF generate):

| model | n | correct | acc | 95% Wilson CI |
|---|---:|---:|---:|---|
| SmolLM2-1.7B-Instruct | 800 | 318 | 0.398 | [0.364, 0.432] |
| Qwen2.5-3B-Instruct | 800 | 515 | 0.644 | [0.610, 0.676] |

Those two intervals **do not overlap**, so on this control they are not a CI-overlap tie. That is **not** yet a ranking-stability result: prompt / seed / vLLM / int4 cells are still running. Phi-3.5-mini control is the next T4 cell. Registry: [`results/registry_paper.jsonl`](results/registry_paper.jsonl).

---

## Design choices that match an evaluations desk

| Constraint | What this harness does | Why it matters at ETH / Apertus |
|---|---|---|
| Replay | Frozen JSONL + YAML + `git_commit` in every manifest | A number without a commit is an anecdote |
| One cause | `compare` prints which knobs actually changed | Template and backend are never ablated together |
| No double template | vLLM gets already-rendered strings | Matches the train-vs-serve failure mode |
| Named incomparability | [`notes/incomparability.md`](notes/incomparability.md) | Hardware, dtype, slice, and sampling are listed, not hidden |
| Intervals | Wilson CI; planned McNemar + Kendall $\tau_b$ | Rank reversals inside overlapping CIs are not evidence |
| Serving | TTFT p95 in the same JSON as accuracy | Eval and latency are one artefact |
| Languages | EN / DE / FR on MGSM, plus HI on the canary | DE/FR are Swiss official languages; HI is a language I work in |

I have not used Slurm on Alps. Colab T4 and a Mac are the cluster I have. The job graph (sweep → registry → skip finished hashes → report) is the same shape as a GPU partition job, shrunk.

---

## What a stranger can verify in 10 minutes

```bash
git clone https://github.com/Shivani767/apertus-eval-prep
cd apertus-eval-prep
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
python -m apertus_eval_prep eval --config configs/smoke.yaml --out results/smoke.json
```

If `python -m venv` errors about a PATH separator, the folder path contains `:`. Clone to `~/apertus-eval-prep` first.

Smoke downloads `Qwen/Qwen2.5-0.5B-Instruct` (~1 GB) and scores 4 items. That proves the pipeline, not the model. Open `results/smoke.json`: model id, git commit, hardware, `chat_template`, backend, per-item generations, accuracy, TTFT.

---

## Commands that produce the artefact

Mac (Hugging Face generate; vLLM does not run on macOS):

```bash
python -m apertus_eval_prep dump-prompts --config configs/default.yaml --out results/prompts_tokenizer.txt
python -m apertus_eval_prep eval --config configs/default.yaml --out results/hf_tokenizer.json
python -m apertus_eval_prep eval --config configs/no_template.yaml --out results/hf_none.json
python -m apertus_eval_prep eval --config configs/mismatched.yaml --out results/hf_mismatched.json
python -m apertus_eval_prep compare results/hf_tokenizer.json results/hf_none.json --out results/compare_template.md
python -m apertus_eval_prep compare results/hf_tokenizer.json results/hf_mismatched.json --out results/compare_mismatch.md
```

GPU / Colab vLLM: [`notebooks/colab_vllm.ipynb`](notebooks/colab_vllm.ipynb)

```bash
pip install -e ".[gpu]"
python -m apertus_eval_prep eval --config configs/vllm.yaml --out results/vllm_tokenizer.json
python -m apertus_eval_prep compare results/hf_tokenizer.json results/vllm_tokenizer.json --out results/compare_backend.md
```

### Ranking matrix (Colab T4)

Open [`notebooks/colab_stability.ipynb`](https://colab.research.google.com/github/Shivani767/apertus-eval-prep/blob/master/notebooks/colab_stability.ipynb). **Do not Run all.** One 800-item cell per session; results copy to Google Drive (`MyDrive/apertus-eval-prep-paper`). Finished `config_hash` rows skip.

```bash
python -m apertus_eval_prep sweep --config configs/experiments/stability.yaml \
  --profile t4 --out-dir results/runs --registry results/registry_paper.jsonl \
  --only-model microsoft/Phi-3.5-mini-instruct --only-factor control
```

`--profile t4` skips 7B fp16 / int8 / vLLM. Do not write the paper matrix into `results/registry.jsonl` (that file is the n=4 smoke).

---

## Mapping onto Apertus Evaluations language

| Job language | This repo |
|---|---|
| `hf` vs `vllm` | `--backend hf` / `--backend vllm` |
| `--chat-template` / `--no-chat-template` | `chat_template: tokenizer \| none \| mismatched` |
| Generation scores can differ across backends | `compare` on committed JSON |
| Jobs that rerun | Frozen JSONL + YAML + git commit |
| TTFT / serving | `latency.ttft_ms_p95` in the same file as accuracy |

What I would do next on a real partition (Alps / CSCS): pin Apertus-8B at a named revision, keep this extractor and OFAT YAML, replace the Colab loop with Slurm array jobs over the same `config_hash` registry. The science does not change; the hardware does.

---

## Slices

| Task | canary n | official n | Why it is here |
|---|---|---|---|
| `arc_easy` | 8 | 200 | English MCQ; Apertus suites include ARC |
| `gsm8k` | 8 | 200 | Verifiable math; backend-sensitive under generation |
| HellaSwag | — | 200 | Generative letter, not loglikelihood |
| multilingual / MGSM | 8 (EN/DE/FR/HI) | 200 (EN/DE/FR) | Swiss languages + a language I work in |
| `template_canary` | 4 | — | Built to fail if the template is missing or wrong |

Canary: [`data/eval_set.jsonl`](data/eval_set.jsonl). Official revisions: [`data/official/SOURCES.md`](data/official/SOURCES.md).

Chat-template modes: `tokenizer` applies `apply_chat_template`; `none` is the raw user string; `mismatched` wraps Llama-3 special tokens around a Qwen prompt.

---

## Layout

```
configs/                  default, smoke, no_template, mismatched, vllm
configs/experiments/      stability.yaml OFAT matrix
paper/stability.md        ranking-study protocol
notes/findings.md         measured canary + backend claims
notes/incomparability.md  when two numbers are not the same experiment
results/registry_paper.jsonl + results/runs/   T4 matrix (partial)
src/apertus_eval_prep/    hf / vLLM backends, sweep, Wilson CI, report
```

---

## Honesty

- I have not run Slurm, Megatron, NCCL, GH200, or Apertus-8B.
- Generative exact-match is not lm-eval loglikelihood and not a headline score.
- n=28 is a serving canary. n=800 control cells are not yet an OFAT ranking table.
- Do not invent GPU numbers. If it is not in git JSON, it did not happen.

## License

Apache-2.0. Evaluation items: [`data/README.md`](data/README.md).
