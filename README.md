# apertus-eval-prep

**Evaluation configuration is part of the measurement.** Chat template, decoding backend, prompt, seed, and precision are named factors, not operator noise.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Shivani767/apertus-eval-prep/blob/master/notebooks/colab_stability.ipynb)

Public frozen-prompt harness: same items, same extractor, Hugging Face `generate` vs vLLM on identical rendered strings, Wilson CIs and TTFT in one JSON. Probe for [swiss-ai evals-post-train](https://github.com/swiss-ai/evals-post-train) (HF vs vLLM on generation) and Apertus serving (`--chat-template-content-format string`). Not Alps. Not `swiss-ai/Apertus-v1.5-8B`.

---

## Abstract

A leaderboard score is a pair *(model, eval config)*. Two labs can disagree on the same weights if the chat template or the serving engine differs. This repo freezes that config in YAML + git, ablates **one factor at a time**, and refuses to mix tables across hardware.

**Hypothesis.** A working measurement pipeline must move when the template or backend changes, in a way a stranger can replay. Rank order is a second question: it needs intervals, not point estimates.

**Status.** Template and backend canaries are done (n=28). Official ranking matrix (n=800, OFAT) is in progress; two T4 control cells are committed.

---

## Results

Do not pool these tables. Device is a confound.

### A. Chat template — Mac MPS, n=28, `Qwen2.5-0.5B-Instruct`

Greedy decode. Only `chat_template` changes.

| condition | overall | ARC | GSM8K | multilingual | canary |
|---|---|---|---|---|---|
| tokenizer (correct) | **20/28 (71.4%)** | 8/8 | 2/8 | 7/8 | 3/4 |
| none | **15/28 (53.6%)** | 5/8 | 2/8 | 5/8 | 3/4 |
| Llama-3 wrap on Qwen | **12/28 (42.9%)** | 4/8 | 2/8 | 5/8 | 1/4 |

GSM8K is 2/8 in all three runs: capability floor on this probe, not a template effect. ARC and the format canary move. The Llama-3 wrap is the serving failure mode (engine default ≠ tokenizer template). [`notes/findings.md`](notes/findings.md)

### B. Backend — Colab T4, template fixed

Same rendered strings. vLLM is not given a second `llm.chat()` wrap.

| backend | overall |
|---|---|
| Hugging Face `generate` | **20/28 (71.4%)** |
| vLLM | **18/28 (64.3%)**, −7.1 pp |

The drop is multilingual (7/8 → 4/8), not ARC. One GSM8K item flipped; n=8, treat as noise. Claim is *not* “vLLM is worse at math.” Claim is: generative exact-match is backend-sensitive; hold the backend fixed when ranking models. [`results/compare_backend.md`](results/compare_backend.md)

### C. Sample size — Wilson 95% CI width

Prefix intervals on already-scored items. No extra GPU jobs. [`reports/ci_width/ci_width.md`](reports/ci_width/ci_width.md)

| run | n | acc | 95% Wilson CI | width |
|---|---:|---:|---|---:|
| T4 smoke | 4 | 0.25 | [0.046, 0.699] | **0.654** |
| Mac canary | 28 | 0.714 | [0.529, 0.848] | **0.318** |

A 25-point gap on n=4 is inside the interval. Point estimates are not ranks.

### D. Ranking matrix — official n=800, OFAT, in progress

Slices: ARC-Easy, GSM8K, HellaSwag, MGSM EN/DE/FR (200 each). Generative exact-match. Control: greedy, tokenizer template, HF generate. Protocol: [`paper/stability.md`](paper/stability.md)

| model | n | correct | acc | 95% Wilson CI |
|---|---:|---:|---:|---|
| SmolLM2-1.7B-Instruct | 800 | 318 | 0.398 | [0.364, 0.432] |
| Qwen2.5-3B-Instruct | 800 | 515 | 0.644 | [0.610, 0.676] |

Intervals do not overlap on this control. That is not ranking *stability*: prompt, seed, vLLM, and quantization cells are still running. Next committed cell: Phi-3.5-mini control. Registry: [`results/registry_paper.jsonl`](results/registry_paper.jsonl)

---

## Method

| Design | Implementation |
|---|---|
| Replay | Frozen JSONL + YAML; `git_commit` in every manifest |
| One cause | `compare` lists knobs that actually changed |
| No double template | vLLM scores already-rendered completion strings |
| Named incomparability | hardware, dtype, slice, sampling listed, not hidden ([`notes/incomparability.md`](notes/incomparability.md)) |
| Intervals | Wilson CI on every run; McNemar + Kendall $\tau_b$ on the ranking matrix |
| Serving | TTFT p95 in the same JSON as accuracy |
| Languages | MGSM EN/DE/FR (official); HI on the canary |

Control and OFAT factors (prompt, seed, backend, int8/int4) are in [`configs/experiments/stability.yaml`](configs/experiments/stability.yaml). T4 profile skips 7B fp16 / int8 / vLLM.

---

## Reproduce

```bash
git clone https://github.com/Shivani767/apertus-eval-prep
cd apertus-eval-prep
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
python -m apertus_eval_prep eval --config configs/smoke.yaml --out results/smoke.json
```

If `venv` fails on a PATH separator, the clone path contains `:`. Use `~/apertus-eval-prep`.

Smoke: `Qwen2.5-0.5B-Instruct`, 4 items. Proves the pipeline. Inspect `results/smoke.json` for model id, commit, hardware, `chat_template`, backend, per-item traces, accuracy, TTFT.

Template ablation (Mac; vLLM is Linux/CUDA):

```bash
python -m apertus_eval_prep eval --config configs/default.yaml --out results/hf_tokenizer.json
python -m apertus_eval_prep eval --config configs/no_template.yaml --out results/hf_none.json
python -m apertus_eval_prep eval --config configs/mismatched.yaml --out results/hf_mismatched.json
python -m apertus_eval_prep compare results/hf_tokenizer.json results/hf_none.json --out results/compare_template.md
```

vLLM ([`notebooks/colab_vllm.ipynb`](notebooks/colab_vllm.ipynb)):

```bash
pip install -e ".[gpu]"
python -m apertus_eval_prep eval --config configs/vllm.yaml --out results/vllm_tokenizer.json
python -m apertus_eval_prep compare results/hf_tokenizer.json results/vllm_tokenizer.json --out results/compare_backend.md
```

Ranking matrix: one 800-item cell per Colab session. Do not Run all. Persist to Drive `MyDrive/apertus-eval-prep-paper`. Do not write paper rows into `results/registry.jsonl` (n=4 smoke).

```bash
python -m apertus_eval_prep sweep --config configs/experiments/stability.yaml \
  --profile t4 --out-dir results/runs --registry results/registry_paper.jsonl \
  --only-model microsoft/Phi-3.5-mini-instruct --only-factor control
```

---

## Slices

| Task | canary n | official n | Role |
|---|---|---|---|
| ARC-Easy | 8 | 200 | English MCQ |
| GSM8K | 8 | 200 | Verifiable math; backend-sensitive under generation |
| HellaSwag | — | 200 | Generative letter (not loglikelihood) |
| MGSM | 8 (EN/DE/FR/HI) | 200 (EN/DE/FR) | Multilingual exact-match |
| template_canary | 4 | — | Fails if the template is missing or wrong |

Canary: [`data/eval_set.jsonl`](data/eval_set.jsonl). Hub revisions: [`data/official/SOURCES.md`](data/official/SOURCES.md). Modes: `tokenizer` = `apply_chat_template`; `none` = raw user string; `mismatched` = Llama-3 tokens on a Qwen prompt.

---

## Scope

- No Slurm, Megatron, NCCL, GH200, or Apertus-8B. Colab T4 / Mac is the cluster.
- Generative exact-match ≠ lm-eval loglikelihood ≠ a model-card headline.
- n=28 is a serving canary. n=800 controls are not yet an OFAT ranking table.
- If it is not in git JSON, it did not happen.

On a real partition the science does not change: pin Apertus-8B at a named revision, keep this extractor and OFAT YAML, replace the Colab loop with array jobs over the same `config_hash` registry.

## License

Apache-2.0. Item licenses: [`data/README.md`](data/README.md).
