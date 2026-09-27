# Held-out configuration generalization — first result

**Status:** DERIVED analysis of `results/registry_paper.jsonl`. No new measurement; every
number below is computed from already-committed registry rows.

**Reproduce:**

```bash
python -m apertus_eval_prep heldout --registry results/registry_paper.jsonl --out reports/heldout
```

## The question

Given a matrix in which *b* configurations have been run, how well can we predict the scores
and the ranking of the configurations we have **not** run? The estimator is fit on the
training configurations only; held-out configurations are used for evaluation and never for
fitting, so the curve is leakage-free by construction.

## The matrix

3 models with at least two measured cells, 11 configurations, 3 missing cells left as
`None` (never zero). `Qwen/Qwen2.5-7B-Instruct` is excluded: a single cell gives it no
within-model spread, so it cannot join a models × configurations matrix.

| configuration | SmolLM2-1.7B | Qwen2.5-3B | Phi-3.5-mini | winner |
|---|---:|---:|---:|---|
| `control=control` | 0.3975 | 0.6438 | 0.6700 | Phi-3.5-mini |
| `seed=1` | 0.3975 | 0.6438 | 0.6700 | Phi-3.5-mini |
| `seed=2` | 0.3975 | 0.6438 | 0.6700 | Phi-3.5-mini |
| `backend=vllm` | 0.4200 | 0.6675 | 0.6713 | Phi-3.5-mini |
| `quantization=int8` | 0.4175 | 0.6475 | 0.6725 | Phi-3.5-mini |
| `quantization=int4` | 0.3862 | 0.6562 | 0.6987 | Phi-3.5-mini |
| `prompt_id=concise` | 0.2325 | 0.5125 | 0.5887 | Phi-3.5-mini |
| **`prompt_id=5shot`** | 0.3425 | **0.6863** | 0.5637 | **Qwen2.5-3B** |
| `sampled=t0.7_seed0` | 0.3625 | 0.6425 | — | Qwen2.5-3B |
| `sampled=t0.7_seed1` | 0.3762 | 0.6500 | — | Qwen2.5-3B |
| `sampled=t0.7_seed2` | 0.3900 | 0.6300 | — | Qwen2.5-3B |

## Result 1 — the budget curve is flat, and that is the finding

| runs spent | held out | score error (MAE) | rank recovery (τ) | decision acc |
|---:|---:|---:|---:|---:|
| 2 | 9 | 0.0298 | 1.000 | 1.000 |
| 3 | 8 | 0.0266 | 1.000 | 1.000 |
| 4 | 7 | 0.0382 | 1.000 | 1.000 |
| 5 | 6 | 0.0194 | 0.333 | 1.000 |
| 6 | 5 | 0.0456 | 0.333 | 1.000 |
| 7 | 4 | 0.0239 | 1.000 | 1.000 |
| 8 | 3 | 0.0223 | 1.000 | 1.000 |
| 9 | 2 | 0.0158 | 1.000 | 1.000 |
| 10 | 1 | 0.0177 | 1.000 | 1.000 |

With as few as **2 of 11 configurations**, the aggregate pairwise decision is recovered
perfectly and the mean score is predicted to within ~0.03 accuracy. Spending more runs does
not measurably improve either.

**This does not mean the matrix is adequate.** It means the *aggregate* is saturated, which
is exactly the condition under which a reliability metric stops being informative. The next
result shows why that matters.

## Result 2 — a reproducible minority escapes every aggregate metric

| model A | model B | A wins | B wins | reversible | minority side wins on |
|---|---|---:|---:|---|---|
| SmolLM2-1.7B | Qwen2.5-3B | 0 | 11 | no | — |
| SmolLM2-1.7B | Phi-3.5-mini | 0 | 8 | no | — |
| **Qwen2.5-3B** | **Phi-3.5-mini** | **1** | **7** | **yes** | `control`, `concise`, `int8`, `int4`, `vllm`, `seed=1`, `seed=2` |

The Qwen/Phi ordering — the exact pair the reversal claim rests on — **is reversible, and
the single configuration that reverses it is `prompt_id=5shot`**. It is not noise: it is the
one configuration, out of seven, in which Qwen-3B wins.

The methodological consequence is the point:

> An aggregate reliability metric can report **perfect** decision accuracy on a ranking that
> one perfectly reproducible configuration overturns. A minority flip does not move a majority
> vote, so the aggregate is blind to it by construction.

Reliability measured on the aggregate is therefore not evidence that a ranking is safe. The
per-configuration view is required, and it is cheap: a count, not a fit.

## What this does and does not establish

**Supports:** on this matrix, aggregate model-selection decisions are predictable from very
few configurations; and aggregate reliability and ranking safety are different properties that
must be reported separately.

**Does not support:** any claim that the matrix is *large enough*; that the finding
generalises beyond these three models; or that two configurations would suffice on a matrix
whose factors interact. The three unmeasured sampled cells for Phi, the excluded 7B model,
and a single contested pair mean this is a **demonstration of the method on one matrix**, not
a measurement of the effect.

## Consistent with prior findings in this repository

- Greedy decoding is exactly seed-invariant here: `seed=1` and `seed=2` reproduce
  `control=control` to four decimal places for all three models. Under temperature-0.7
  sampling, per-item outcomes churn while the aggregate barely moves.
- Only one of three pairs is contestable at all: Qwen-3B beats SmolLM2 on all 11
  configurations and Phi beats SmolLM2 on all 8 where both are measured.

## Next

- Re-run this curve on the 7-model curated cohort (`results/colab_real_model/`) as an
  independent replication.
- Extend to the interaction/factorial matrix, where the configuration space is not
  one-factor.
- Fix the chat-template protocol first. The curated cohort's core scores are currently
  depressed by an answer-extraction artefact, and a held-out curve over a broken metric
  would measure the artefact rather than the models.
