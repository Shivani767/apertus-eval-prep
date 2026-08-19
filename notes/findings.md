# Findings

Frozen 28-item slice, `Qwen/Qwen2.5-0.5B-Instruct`, greedy decode (`max_new_tokens=96`, seed 0).
Numbers below are copied from `results/*.json` and `results/compare_*.md`. They are a **regression canary**, not a model-card score.

Two experiments. Do not mix them: hardware and backend are not the same knob.

---

## Experiment 1 — chat template (Mac, Hugging Face generate, Apple MPS)

Control: same binary, same weights, same tokenizer, same 28 items. The only setting that changes is `chat_template`.

| file | `chat_template` | overall | ARC | GSM8K | multilingual | canary |
|---|---|---|---|---|---|---|
| `hf_tokenizer.json` | tokenizer (correct) | **20/28 (71.4%)** | 8/8 | 2/8 | 7/8 | 3/4 |
| `hf_none.json` | none | **15/28 (53.6%)** | 5/8 | 2/8 | 5/8 | 3/4 |
| `hf_mismatched.json` | Llama-3 wrap on Qwen | **12/28 (42.9%)** | 4/8 | 2/8 | 5/8 | 1/4 |

**Claim.** Omitting the instruct template, or applying the wrong family's special tokens, moves accuracy on this slice. The mismatched Llama-3 wrap is the serving bug: the engine's default template is not the tokenizer's template.

**What did not move.** GSM8K stayed **2/8 (25%)** in all three runs. On a 0.5B model that is a capability floor, not a template effect. The two items that stay correct (`gsm8k_004` area, `gsm8k_007` grouping) are the shortest arithmetic.

**What moved.**

- ARC: 8/8 → 5/8 (none) → 4/8 (mismatched). Letter extraction breaks when the model is no longer in chat format.
- multilingual: 7/8 → 5/8 for both ablations. `ml_hi_002` is wrong in every template condition (predicted 14 / 1 / 12, gold 8).
- canary: 3/4 with the real template **and** with none; **1/4** with the Llama-3 wrap. `canary_004` (must share chat template and special tokens) fails unless the Qwen template is applied. That item is doing the job it was written for.

Rendered prompts: `results/prompts_tokenizer.txt`, `prompts_none.txt`, `prompts_mismatched.txt`.

UTC: 2026-08-19. Device: Apple MPS, `dtype: auto`. `git_commit` is null on these three files (runs happened before the first commit). Re-runs after `main` would fill that field; the item golds would not change.

---

## Experiment 2 — backend (Colab Tesla T4, template = tokenizer)

Control: same rendered completion strings, same weights, same T4. The only setting `compare` reports as different is `backend`.

| file | backend | overall | ARC | GSM8K | multilingual | canary |
|---|---|---|---|---|---|---|
| `hf_tokenizer_colab.json` (see note) | hf | **20/28 (71.4%)** | 8/8 | 2/8 | 7/8 | 3/4 |
| `vllm_tokenizer.json` | vllm | **18/28 (64.3%)** | 8/8 | 3/8 | 4/8 | 3/4 |

Source table: `results/compare_backend.md`. Delta overall **−7.1 points** (vLLM − HF).

**Claim.** Hugging Face `generate` and vLLM are not interchangeable on generative tasks even when the chat template is applied in this repo (completion mode, no second `llm.chat()`). That matches the warning in [swiss-ai/evals-post-train](https://github.com/swiss-ai/evals-post-train): GSM8K-style generation can differ across backends; compare models with a **fixed** backend.

**Do not read “vLLM is better at GSM8K.”** GSM8K went 2/8 → 3/8. One extra item (`gsm8k_005`, gold 25) flipped. On n=8 that is noise, not a math-engine ranking.

**Where the −7 points actually are.** ARC and the canary did not move (8/8 and 3/4). Multilingual went **7/8 → 4/8 (−37.5 points)**. vLLM missed the second item in EN/DE/FR (`ml_*_002`, empty tram seats, gold 8; predicted 18/10/10). HF on the T4 got those three right. `ml_hi_002` is wrong on both backends.

**Note on `hf_tokenizer_colab.json`.** The compare file was produced on Colab from that JSON. It was not copied into this tree. Mac `hf_tokenizer.json` is the same overall (20/28) and the same task accuracies, but it is **MPS, not T4**, so it is not the backend control. Use `compare_backend.md` for the backend claim, not Mac JSON vs Colab vLLM.

**vLLM latency fields are empty.** `ttft_ms_*` and `tokens_per_sec_mean` are null / 0 in `vllm_tokenizer.json`. This vLLM build did not populate `RequestOutput.metrics` the way the harness expected. HF on the T4 did: TTFT p95 192.6 ms, ~17 tok/s. Do not invent a vLLM p95. Scores are still valid.

vLLM log (not in JSON): T4 compute 7.5, fallback `float16` (not bfloat16), FlashAttention v2 skipped. `dtype: auto` resolved to float16. Manifest `git_commit` `0382025`, `git_dirty: true` (Colab patched dtype in the working tree).

---

## What would make these numbers incomparable

Full list: `notes/incomparability.md`. The ones that actually apply here:

1. **Mac vs T4.** Experiment 1 is MPS float16-class; experiment 2 is CUDA float16 on a T4. Do not quote 71.4% (Mac template) against 64.3% (Colab vLLM) as a single-knob effect.
2. **Backend + template together.** Never. Template table is HF-only. Backend table is tokenizer-template-only.
3. **n=28.** One flipped GSM8K item is 12.5 points on that task. Treat task deltas as diagnostic, not as a league table.
4. **Missing Colab HF JSON in git.** The backend table exists; the per-item HF-on-T4 traces are not in `results/`. Re-download that file if a reviewer wants byte-for-byte Colab HF.
5. **vLLM TTFT.** Absent. Do not compare serving latency across backends with this JSON.

---

## What this is not

- Not Alps, not Slurm, not `swiss-ai/Apertus-v1.5-8B`.
- Not lm-eval-harness / lighteval (that would be a follow-up with a named `gsm8k` run).
- Not a claim that Qwen2.5-0.5B is a multilingual system. It is a small instruct model used as a probe.

The probe question is: **did the measurement pipeline notice when the template or the backend changed?** Yes.
