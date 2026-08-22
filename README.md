# apertus-eval-prep

**Evaluation configuration is part of the measurement.** Chat template, decoding backend, prompt, seed, and precision are named factors, not operator noise.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Shivani767/apertus-eval-prep/blob/master/notebooks/colab_stability.ipynb)

Public frozen-prompt harness: same items, same extractor, Hugging Face `generate` vs vLLM on identical rendered strings, Wilson CIs and TTFT in one JSON. Probe for [swiss-ai evals-post-train](https://github.com/swiss-ai/evals-post-train) (HF vs vLLM on generation) and Apertus serving (`--chat-template-content-format string`). Not Alps. Not `swiss-ai/Apertus-v1.5-8B`.

---

## Abstract

A leaderboard score is a pair *(model, eval config)*. Two labs can disagree on the same weights if the chat template or the serving engine differs. This repo freezes that config in YAML + git, ablates **one factor at a time**, and refuses to mix tables across hardware.

**Hypothesis.** A working measurement pipeline must move when the template or backend changes, in a way a stranger can replay. Rank order is a second question: it needs intervals, not point estimates.

**One finding (n=800, committed JSON).** On SmolLM2-1.7B, only `prompt_id` changes: default 318/800 (0.398, [0.364, 0.432]) → concise 186/800 (0.232, [0.204, 0.263]). Intervals are disjoint. GSM8K 64/200 → 10/200; MGSM 44/200 → 9/200. A shorter prompt is not a free speedup; it breaks exact-match math. `5shot` (274/800) overlaps the control interval — a null on the overall CI, not a win.

**Status.** Canaries A–C done. Paper matrix **5 / 34** T4 cells in git; Qwen-7B int4 in flight. Kendall $\tau_b$ / McNemar across models are **not** reported yet (need Qwen + Phi `prompt_id`). Calendar: [`paper/remaining.md`](paper/remaining.md).

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
| Phi-3.5-mini-instruct | 800 | 536 | 0.670 | [0.637, 0.702] |

SmolLM2 is separated from the other two. Phi and Qwen-3B **overlap** on this control (67.0% vs 64.4% is not a rank). Registry: [`results/registry_paper.jsonl`](results/registry_paper.jsonl)

**D2. SmolLM2 only — `prompt_id` (same weights, T4, control otherwise).** First OFAT factor. Do not treat this as a three-model rank.

| prompt | correct | acc | 95% Wilson CI |
|---|---:|---:|---|
| default (control) | 318 | 0.398 | [0.364, 0.432] |
| concise | 186 | 0.232 | [0.204, 0.263] |
| 5shot | 274 | 0.342 | [0.310, 0.376] |

`concise` does not overlap control (−16.5 pp). The drop is math: GSM8K 64→10, MGSM 44→9. `5shot` overlaps control on the overall interval. Prompt wording is a first-class knob on this model; Qwen/Phi `prompt_id` cells are still needed before any rank-reversal claim.

---

## Method

| Design | Implementation |
|---|---|
| Replay | Frozen JSONL + YAML; `git_commit` in every manifest |
| One cause | `compare` lists knobs that actually changed |
| No double template | vLLM scores already-rendered completion strings |
| Named incomparability | hardware, dtype, slice, sampling listed, not hidden ([`notes/incomparability.md`](notes/incomparability.md)) |
| Intervals | Wilson CI on every committed run; McNemar + Kendall $\tau_b$ **implemented and unit-tested**, filled in after the same factor exists on all three fp16 models |
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

`pytest` covers scoring, Wilson / McNemar / Kendall $\tau_b$, OFAT expansion and T4 skips, official-slice provenance, HF Phi cache shim, and mid-run checkpoint resume (`tests/test_*.py`). That is the 10-minute trust check. Smoke then downloads `Qwen2.5-0.5B-Instruct` and scores 4 items. Inspect `results/smoke.json` for model id, commit, hardware, `chat_template`, backend, per-item traces, accuracy, TTFT.

If `venv` fails on a PATH separator, the clone path contains `:`. Use `~/apertus-eval-prep`.

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

Ranking matrix: one 800-item cell per Colab session. Do not Run all. Persist to Drive `MyDrive/apertus-eval-prep-paper`. Do not write paper rows into `results/registry.jsonl` (n=4 smoke). Interrupted cells write `results/runs/{run_id}.partial.jsonl` after every item and mirror it to Drive; re-run the same sweep to resume. Notebook stdout is not a result.

```bash
python -m apertus_eval_prep sweep --config configs/experiments/stability.yaml \
  --profile t4 --out-dir results/runs --registry results/registry_paper.jsonl \
  --only-model HuggingFaceTB/SmolLM2-1.7B-Instruct --only-factor prompt_id
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
- n=28 is a serving canary. 5 / 34 paper cells are not a Kendall table.
- If it is not in git JSON, it did not happen.

On a real partition the science does not change: pin Apertus-8B at a named revision, keep this extractor and OFAT YAML, replace the Colab loop with array jobs over the same `config_hash` registry.

---

## Remaining GPU time (Colab T4)

Full schedule: [`paper/remaining.md`](paper/remaining.md). Protocol: [`paper/stability.md`](paper/stability.md). Cite: [`CITATION.cff`](CITATION.cff).

| Milestone | Cells still needed | Est. T4 hours | Calendar (1 free GPU) | Calendar (2 free GPUs) |
|---|---:|---:|---|---|
| **Now** | 0 | 0 | — | 5 cells in git |
| **Minimum note** (Qwen + Phi `prompt_id`) | 4 | 10–14 | 5–8 days | 3–5 days |
| Finish 7B int4 | 1 (running) | 0–4 | +1 day | in flight |
| **Full 34-cell T4 matrix** | 29 | **50–70** | **4–7 weeks** | **3–5 weeks** |
| 2–4 page write-up | 0 | 0 | 1–2 days after the minimum note | same |

Notebook: run **one** `--only-factor` cell per session. Never the “remaining * factors” cells. After Qwen + Phi `prompt_id` land, `report` / `paper-tables` on `registry_paper.jsonl` produce Kendall $\tau_b$ and McNemar. Nulls stay null.

---

## Not claimed (roadmap after the matrix)

These are the right next papers. They are **not** in the 34-cell clock and are not in git as results.

| Audience | Add later | Why |
|---|---|---|
| ETH / swiss-ai | `swiss-ai/Apertus-v1.5-8B` at a pinned revision (int4 on T4); MGSM **IT**; issue/PR on [evals-post-train](https://github.com/swiss-ai/evals-post-train) with the HF vs vLLM JSON | Same job on their weights and languages |
| MSR / eval infra | Optional lm-eval backend; paraphrase / prompt-perturbation arm; Azure ML batch over the same `config_hash` | Serving-eval mismatch at scale |
| Indic / Sarvam | MILU or IndicGLUE items (ta/te/bn/mr/pa/gu); tokenizer-fertility vs TTFT | Hindi-only canary is underweighted for that desk |

Do not put Apertus-8B or Italian numbers in a cover letter until they exist as run JSON.

## License

Apache-2.0. Item licenses: [`data/README.md`](data/README.md).
