# Decision stability

## What this measures

Three questions are easy to confuse and answer different things:

| Question | Metric | Module |
|---|---|---|
| Does the score move? | score stability | `stability.py` |
| Does the ordering move? | ranking stability | `ranking.py` |
| **Does the selected option change?** | **decision stability** | `decision.py` |

They are not substitutes. A ranking can churn while the selected model never
changes, and a ranking can look stable while the decision flips because the
winner moved inside the noise band. Only the third is the thing an engineer
actually acts on, so it gets measured directly rather than inferred.

## The policy is data

There is no hard-coded notion of "the right decision". A policy declares its
objectives with explicit directions and its constraints with explicit bounds:

```yaml
decision_policy:
  name: balanced_quality_cost
  objectives:
    quality: max
    cost: min
  constraints:
    quality: 0.65          # floor
    max_cost: 0.02         # ceiling
```

Constraint language is shared with `platform-select` and `metrics.pareto`, so a
policy written here means the same thing there. Direction is always explicit:
a latency ceiling can never silently become a floor.

## Resolution order

`decide()` records *how* a decision was reached, not just that one appeared:

1. filter by constraint;
2. one survivor → that is the decision (`unique_eligible`);
3. otherwise take the Pareto frontier of the eligible set;
4. one frontier member → that is the decision (`pareto_unique`);
5. several → `tie`.

A trade-off is a tie, never an arbitrary winner. In the shipped fixture,
`model_a` is more accurate and `model_b` is cheaper; nothing dominates, so the
honest output is "these tie", and inventing a winner there would be an
unsupported claim.

## The metric

```
decision_stability = same_decision / valid_configurations
```

The denominator is stated in every artifact because it decides the headline
number. A configuration is **valid** when the policy produced a determinable
outcome: a unique decision, a tie set, or a deliberate "nothing is eligible".

| Outcome | Counted as | Meaning |
|---|---|---|
| `same_decision` | numerator | selected the baseline option again |
| `tie_includes_baseline` | denominator, not numerator | baseline is still tied for best |
| `decision_reversal` | denominator, not numerator | a different option was selected |
| `no_eligible_option` | denominator, not numerator | nothing met the constraints |
| `invalid_configuration` | **excluded** | an objective was never measured |

`stability_allowing_ties` is reported alongside and never merged into
`stability`. A tie containing the baseline is weaker than a unique repeat but
is not a reversal, and the reader should be able to see both readings instead of
having one imposed.

## Missing evidence is never zero

An objective that was never measured yields `insufficient_evidence`. The
configuration is excluded from the denominator and listed with its reason. It
is never read as a score of 0 — a fake zero would pass a cost ceiling and win
the min-cost objective outright — and a missing metric never counts as a
reversal.

## When the baseline does not decide

If the baseline configuration itself yields no decision, the artifact reports
`status: insufficient_design` and `stability: null`. Stability relative to a
non-decision is undefined; a number there would be an artifact of which cell
happened to be the baseline.

## Reversal causes are associations

When configurations declare their `factors`, reversals are attributed to the
factor levels that differ from the baseline. A factor counts as *changed* only
when both configurations declare it and the levels differ. A key present on one
side only is a difference in metadata completeness, not evidence of a
perturbation, and is reported under `undeclared_factors`.

Every cause carries `causal_claim: false` and an `attribution_quality`:

| Attribution | Meaning |
|---|---|
| `single_factor` | one declared factor differs; localisable under OFAT |
| `single_factor_incomplete_metadata` | one factor differs, other keys undeclared on one side |
| `multi_factor_confounded` | several factors differ; **not** an explanation |
| `unknown` | nothing can be localised |

`reversal_cause_design` summarises the whole set (`single_factor`, `mixed`,
`confounded`, `insufficient_metadata`) so a reader cannot mistake a confounded
breakdown for a clean one.

## Usage

```bash
apertus-eval-prep decision-stability \
  --configurations reports/decision_stability/configurations.json \
  --policy configs/decision_policies/example.yaml \
  --evidence-mode LOCAL_REAL_MODEL \
  --out reports/decision_stability/decision_stability.json
```

`--evidence-mode` is an explicit choice from the canonical evidence list and
defaults to `UNKNOWN`. It is never inferred upward, so a MOCK sweep cannot be
reported as a real-model result.

## What this does not claim

Decision stability is an engineering policy aid. It is not production approval,
model certification, or a causal explanation. Stability under the evaluated
configurations does not establish stability under unevaluated ones, and a high
stability figure says nothing about whether the selected option is good — only
that the selection did not move.
