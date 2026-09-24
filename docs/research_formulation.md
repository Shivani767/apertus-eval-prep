# Research Formulation

**Date:** 2026-12-09

This document formalizes the research model that turns Apertus from *an LLM
evaluation framework* into *a research system for measuring, predicting, and
efficiently reducing uncertainty in LLM model comparisons caused by evaluation
configuration*.

## 1. Central research question

> **Can we trust an LLM model comparison when reasonable evaluation
> conditions change?**

An LLM benchmark result is not a pure property of the model. It is an
observation of a *model interacting with an evaluation configuration* — the
prompt, decoding strategy, inference backend, quantization, chat template,
hardware, and dataset revision — plus measurement noise. Apertus makes that
configuration an explicit, hashable part of the measurement and studies how
scores, rankings, and downstream model-selection decisions move under
reasonable configuration shifts.

## 2. Evaluation configuration

An evaluation configuration is the tuple

```
C = (prompt,
     few_shot,
     backend,
     quantization,
     decoding,
     seed,
     chat_template,
     runtime,
     hardware,
     model_revision,
     dataset_revision)
```

Each coordinate is a *level* taken from a finite (in practice enumerable) set:

| Coordinate | Meaning | Example levels (this repo) |
|---|---|---|
| `prompt` | prompt family wording | `default`, `concise`, `5shot`, paraphrase variants |
| `few_shot` | few-shot demonstration source | `none`, `data/official/fewshot.jsonl` |
| `backend` | inference engine | `hf`, `vllm` |
| `quantization` | weight precision | `none` (fp16), `int8`, `int4` |
| `decoding` | sampling policy | greedy (T=0), sampled (T=0.7, top_p=0.95) |
| `seed` | PRNG seed for sampling | 0, 1, 2 |
| `chat_template` | template used to render turns | `tokenizer`, `none`, `mismatched` |
| `runtime` | runtime knobs that change serving behavior | `max_new_tokens`, dtype |
| `hardware` | GPU / platform | Tesla T4, A10, Apple MPS |
| `model_revision` | pinned model checkpoint | HF revision or `UNAVAILABLE` |
| `dataset_revision` | pinned evaluation items | sha256 fingerprint in `data/catalog/` |

The *configuration space* of an experiment is its contemplated set of
configurations `{C_1, ..., C_K} ∪ {C_control}`. It is defined in a study YAML
and materialized deterministically by the interaction/held-out subsystems.

## 3. Score model

Conceptually, the observed score is

```
Y = f(M, T, C) + ε
```

where

- `M` ∈ models,
- `T` ∈ tasks/benchmarks,
- `C` ∈ configuration space,
- `f(M, T, C)` is the *systematic* part of the measurement (a fixed latent
  "signal" of model × task under configuration `C`), and
- `ε` is per-item measurement noise (item sampling, decoding stochasticity
  not captured by `C`).

**Causal overclaim guard.** We do *not* claim that `f` is a stable latent
property that would be the same under any other configuration distribution.
Every statement in this project is about **configuration-induced variation,
sensitivity, association, variance contribution, and ranking instability** —
not about a model-invariant "true" capability. Specifically we say:

- a factor *contributes variance* or *is associated with* score/ranking
  movement on the evaluated configuration distribution;
- a model *appears to* perform better under configuration `C` (measured),
## 4. The three stability objects

### 4.1 Score stability
How much the measured score moves across configurations:

```
SD_C(Y(M,T,·)), range, coefficient of variation, bootstrap CI of the mean
```

### 4.2 Ranking stability
How much model ordering moves across configurations:

```
Kendall τ_b / Spearman ρ between reference and alternative rankings,
rank-reversal probability, top-k membership stability
```

### 4.3 Decision reliability (the central new concept)

For a decision problem "is A better than B?" define

```
DecisionReliability(A, B) = P( A > B | C ~ P(C) )
```

where `P(C)` is an **explicitly defined evaluation-configuration
distribution** (e.g. the empirical distribution of observed configurations,
or a specified uniform/stratified distribution over the configuration space).
In practice we estimate this by bootstrap resampling configurations from the
observed set:

```
P̂(A > B) = (1/B) Σ_b 𝟙[ score(A, C*_b) > score(B, C*_b) ]
```

where `C*_b` is a resample of configurations, and ties are handled by a
documented convention (not wins; reported separately).

**Assumptions (stated, never silent):**

1. Observed configurations are treated as an i.i.d. sample from `P(C)`
   (a modeling assumption; violated by convenience-based sampling).
2. Per-cell scores carry their own measurement noise (Wilson CI), ignored in
   the point-estimate comparison unless a CI-aware decision rule is used.
3. The decision problem is pairwise; joint decisions over > 2 models are
   derived from pairwise quantities and labeled as such.

## 5. Reliability estimation and its prediction target

The composite **Evaluation Reliability Score (ERS)** is a *provisional
descriptive summary* built from observed statistics (see `reliability.py`).
It is **not** a calibrated probability.

The formal prediction target for validation is

```
out-of-sample ranking stability:
    P( ranking_order(A,B) is preserved | C_test )
```

where `C_test` is hidden while the estimator is fit on `C_train`. The
reliability estimator is validated by comparing its predictions to *actual*
behavior on `C_test` using:

- calibration (ECE, reliability diagram),
- Brier score and log loss for pairwise decisions,
- AUROC for binary pairwise *ordering correct* classification,
- ranking correlation between predicted and actual ranking instability,
- confidence-interval coverage.

ERS's validity claim is restricted to the evaluated configuration
distribution and experimental setting. It is never "ground truth".

## 6. Interaction model for factorial experiments

For a two-factor experiment with factors `a ∈ A`, `b ∈ B`, and a balanced,
complete design, we decompose the score as

```
Y_ijk = μ + α_i + β_j + (αβ)_ij + ε_ijk
```

with identifying sum-to-zero constraints, and report:

- main-effect variance fractions `SS_α / SS_total`, `SS_β / SS_total`,
- interaction fraction `SS_αβ / SS_total`,
- residual `SS_ε / SS_total`,
- bootstrap CIs and diagnostics (balance, completeness).

We apply ANOVA **only** where the design justifies it: balanced, complete,
independent cells. Otherwise the analysis returns `UNAVAILABLE` with the
reason (same policy as `variance.interaction_screen`).

## 7. Adaptive evaluation (Apertus-R)

Apertus-R selects the next configuration to evaluate under a fixed budget
using a documented heuristic acquisition function

```
Utility(c) ≈ ExpectedDecisionUncertaintyReduction(c) / EvaluationCost(c)
```

The uncertainty-reduction term is operationalized with quantities computed
from already-measured configs (pairwise decision uncertainty, per-model
spread, CI overlap), and the cost term uses measured latency / DERIVED
`est_total_s` where available or a documented default. This is a
**heuristic**; we do not claim optimality unless a later experiment
establishes it. Every strategy (random, OFAT, Apertus-R, LHS where supported)
receives the same budget in head-to-head comparisons.

## 8. The full research workflow

```
configuration space
  → held-out split (C_train | C_test, deterministic, leakage-free)
  → measurements on C_train
  → score variance
  → ranking instability
  → interaction effects (factorial cells)
  → reliability estimate (ERS components, pairwise P(A>B))
  → prediction for C_test
  → comparison with actual held-out behavior (calibration, ranking recovery)
  → budget-aware adaptive selection (Apertus-R vs baselines)
  → budget curves (ranking recovery vs. evaluations)
  → generalization probes (held-out models / tasks)
  → failure atlas (why did apparent performance change?)
  → reproducible paper artifacts
```

The overarching claim supported by this system is deliberately modest until
experiments establish more:

> "LLM benchmark results should be treated as measurements with
> configuration-dependent uncertainty, and reliable model comparisons can
> potentially be obtained with substantially fewer evaluations when evaluation
> configurations are selected based on uncertainty and decision value."

The words **can potentially** remain until the budget-curve and generalization
evidence justifies a stronger claim.

## 9. Language rules

| Say | Avoid claiming |
|---|---|
| configuration-induced variation | causal effect on "true" capability |
| sensitivity / association | cause (unless a controlled factorial design) |
| variance contribution | the model *is* better |
| ranking instability | a stable model ordering |
| appears to perform better under C | performs better, period |

## 10. Related-work distinction

Previous work tends to ask *"which evaluations need to be run?"* (benchmark
selection, mini-benchmarks, adaptive test design over tasks/items). Apertus
asks a different question:

> **Which evaluation configurations need to be run before we can trust a
> model comparison?**

This claim is only made to the extent the literature review in
`paper/RELATED_WORK.md` and the paper's related-work section supports it.
  not that it *is* better in a configuration-free sense.