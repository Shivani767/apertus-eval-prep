# Ranking stability

## Why there is no single stability score

`ranking.py` reports several ordering-agreement metrics side by side and
deliberately does **not** collapse them into one number. The reason is
empirical: they disagree, and which disagreement matters depends on how many
models a deployment actually ships.

From the deterministic fixture in `tests/test_ranking_stability.py`, where one
perturbation swaps only the top pair:

| Metric | Value | Reading |
|---|---|---|
| `top_1_stability` | 0.00 | shipping the single best model would have been a coin flip |
| `top_k_stability` (k=2) | 1.00 | the deployed *pair* never changed |
| `mean_kendall_tau` | 0.33 | overall ordering agreement is partial |
| `mean_pairwise_inversion_rate` | 0.33 | one of three pairs inverted |

A composite would have to average these into a single figure and pick a
weighting that encodes a decision the platform cannot justify. The top-2
deployment was perfectly stable while the top-1 deployment was not — that
disagreement *is* the finding, and averaging would erase it.

`composite_score` is therefore always `null`, with the rationale recorded in
the artifact.

## Definitions

| Metric | Definition |
|---|---|
| `rank_reversal_rate` | changed best-first orderings / valid perturbations |
| `top_1_stability` | valid perturbations keeping the same leader |
| `top_k_stability` | valid perturbations preserving the same top-k **set** |
| `top_k_exact_order_stability` | valid perturbations preserving top-k **and its order** |
| `mean_kendall_tau` | mean Kendall tau-b vs baseline ordering |
| `mean_pairwise_inversion_rate` | mean discordant pairs / total pairs |

Top-k is **set-based** on purpose: swapping ranks 1 and 2 is still the same
selection when a deployment only ships the top two. The exact-order variant is
reported alongside so both readings are available.

## The denominator

A perturbation is *valid* when it scored the same model set as the baseline. A
column with an unmeasured cell is recorded in `incomparable` and **excluded**
from the denominator — a model that was never measured is not evidence that the
ranking held.

Zero valid perturbations yields `rank_reversal_rate: null`, not `0.0`. Zero
reversions out of zero measurements is not evidence of stability.

Ties are broken by model name so ordering is deterministic; a tied pair
contributes a stable order rather than an arbitrary one.

## Pre-existing metrics

The following were already in `ranking.py` and are reused, not duplicated:
`spearman_rank_correlation`, `pairwise_win_rates`, `rank_distributions`,
`bootstrap_ranking_stability`. Pair counting reuses
`stats.pairwise_reversals` and rank vectors use `stats.rank_high_is_better`, so
there is one definition of a rank in the codebase.

## Usage

```bash
apertus-eval-prep ranking-stability \
  --matrix reports/ranking_stability/matrix.json \
  --k 2 \
  --evidence-mode LOCAL_REAL_MODEL \
  --out reports/ranking_stability/ranking_stability.json
```

The input is a score matrix committed by earlier runs: one row per model, one
column per configuration, `null` for an unmeasured cell. `--baseline-config`
selects the reference column (default 0) and is rejected if out of range.

## What this does not claim

These are engineering diagnostics describing ordering agreement across
evaluated configurations. They are not a model quality judgement, a statistical
test, or production approval. Kendall tau and inversion rate describe the
*ordering*, not the size of the gaps: two configurations can produce a fully
stable ranking while the underlying accuracies move substantially. Read
`stability.py` and the score intervals alongside these numbers, never instead
of them.
