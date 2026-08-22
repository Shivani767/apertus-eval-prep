# Remaining Colab work and calendar

T4 profile = **34** cells × 800 items. Do not Run all. One `--only-factor` (or the 7B cell) per session. Registry: [`results/registry_paper.jsonl`](../results/registry_paper.jsonl). Notebook: [`notebooks/colab_stability.ipynb`](../notebooks/colab_stability.ipynb).

Hours are wall-clock on a free Tesla T4 from runs already finished in this repo. Free Colab often dies at 1–2 hours; `.partial.jsonl` on Drive resumes. Two Google accounts in parallel help only if they run **different** `config_hash` rows and do **not** share a Drive folder while both write.

## Scoreboard (2026-08-22)

| State | Cells | What |
|---|---:|---|
| **In git** | **5 / 34** | 3× control (SmolLM2, Qwen-3B, Phi) + SmolLM2 `prompt_id` (concise, 5shot) |
| **In flight** | **1** | Qwen-7B **int4** (other Colab; not in git until `[800/800]` + zip) |
| **Not started** | **28** | see list below |

Kendall $\tau_b$ and McNemar across models are **not** computed yet. They need the same factor on **all three** fp16 models. Wilson CIs on committed JSON are real.

## What the notebook still has to run

**Do not run** the three “remaining * factors” cells. Each is 8–10 jobs.

| Notebook cell | Jobs left | Est. T4 time | When |
|---|---:|---|---|
| Qwen-7B (T4 int4 only) | 1 | 3–5 h | already started on the second account |
| Qwen-3B `prompt_id` | 2 | 5–7 h | **next on a free GPU** (needed for a prompt-rank claim) |
| Phi `prompt_id` | 2 | 5–7 h | after Qwen prompt, or second account after 7B |
| SmolLM2 `seed` | 2 | 0.5–1 h | leftover quota on the 1.7B account |
| SmolLM2 `backend` (vLLM) | 1 | 0.5–1 h | after seed |
| SmolLM2 `quantization` | 2 | 1–2 h | int8 + int4 |
| SmolLM2 `sampled` | 3 | 1–2 h | last SmolLM2 factor |
| Qwen-3B seed / vLLM / quant / sampled | 8 | 18–24 h | after that model’s `prompt_id` |
| Phi seed / vLLM / quant / sampled | 8 | 18–24 h | after that model’s `prompt_id` |

Phi and Qwen **control** cells should `skip` after `git pull`. SmolLM2 **control** and **prompt_id** should `skip`.

## Time to a result a reviewer can cite

| Milestone | GPU left | Calendar (1 free T4) | Calendar (2 free T4s) | What you can write |
|---|---|---|---|---|
| **Now** (committed) | 0 | — | — | Template −28.5 pp (n=28). Backend −7.1 pp, multilingual (n=28). SmolLM2 concise −16.5 pp, math collapses (n=800). Phi vs Qwen-3B **overlap** on control. |
| **Minimum note** | ~10–14 h | **5–8 days** | **3–5 days** | Same `prompt_id` on Qwen-3B + Phi. Then McNemar (paired items) and whether the control **order** (Smol ≪ Qwen ~ Phi) holds. First Kendall $\tau_b$ on three models, one factor. |
| **+ 7B int4** | +0–4 h | +1 day | in flight | int4 cohort row. Not comparable to fp16 controls. |
| **Full T4 matrix** | **~50–70 h** | **4–7 weeks** | **3–5 weeks** | All 34 cells. Forest plot, Kendall per factor, rank heatmap. Nulls (e.g. greedy seed) reported as nulls. |
| **Write-up** | 0 GPU | **1–2 days** after minimum note | same | 2–4 page technical note + `paper-tables` from `registry_paper.jsonl`. |

Apertus-8B, Italian/Romansh slices, lm-eval bridge, Indic expansion, Azure: **not** in the 34-cell clock. Those are a second project after the matrix (or a named add-on). See README roadmap.

## Hour model (how the 50–70 h is built)

| Class | Per 800-item cell | Remaining cells | Subtotal |
|---|---|---:|---|
| SmolLM2 1.7B fp16 | 15–40 min | 8 | ~3–5 h |
| Qwen-3B / Phi ~3–4B fp16 | 2–3.5 h | 20 | ~40–70 h |
| Qwen-7B int4 | 3–5 h | 1 | ~3–5 h |

Use the low end if most items are short ARC letters; the high end if GSM8K/MGSM decode to `max_new_tokens=256`. Quota death and re-download add ~20%.

## Suggested order (highest scientific value first)

1. Finish 7B int4; commit JSON (do not duplicate on two accounts).
2. Qwen-3B `prompt_id`, then Phi `prompt_id` — **minimum note**.
3. SmolLM2 `seed` (cheap; tests whether greedy seed is a no-op).
4. One `backend=vllm` cell per fp16 model (swiss-ai warning, n=800).
5. Quantization and sampled last (memory / time).

After step 2: run

```bash
python -m apertus_eval_prep report --registry results/registry_paper.jsonl --out reports/stability_paper
python -m apertus_eval_prep paper-tables --registry results/registry_paper.jsonl --out paper/_generated_tables.md
```

Do not type Kendall / McNemar by hand. If a factor is null, leave it null.
