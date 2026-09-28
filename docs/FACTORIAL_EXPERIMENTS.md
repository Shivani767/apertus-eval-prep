# Factorial experiments and interaction analysis

## The distinction this module exists to protect

| | OFAT | Factorial |
|---|---|---|
| Design | one factor varies at a time from a shared control | factors crossed, every level combination run |
| Cell where both factors differ | **never run** | measured |
| Main effect | average over the other factor's levels | marginal mean |
| Interaction | **structurally unmeasurable** | estimable |
| Design kind in artifact | `ofat` | `factorial` |

The failure this prevents is specific and common: running a main-effects
analysis over OFAT data and reporting *"no interaction detected."* That is not
a null result. In an OFAT design the interaction was never measured, so the
honest output is that the design cannot answer the question. `analyse_interactions`
labels `design_kind` at the top level of the artifact so this cannot be missed
by a reader who only skims the pair detail.

`interaction.py` builds the crossed cells and is unchanged; this is the
analysis layer on top of it.

## What is reported

For each requested factor pair, when the design permits it:

| Field | Meaning |
|---|---|
| `omega2_pct` | effect size — share of variance explained |
| `variance_fraction` | same quantity, unscaled |
| `f`, `df_numerator`, `df_denominator` | test statistic and degrees of freedom |
| `p_value` | uncorrected |
| `p_value_corrected` | after a declared multiple-comparison correction |
| `bootstrap_ci95_pct` | seeded cell-stratified bootstrap interval |
| `status`, `reason` | why a term is unavailable, when it is |

Main effect, interaction, effect magnitude, uncertainty and significance stay
**separate fields**. The artifact's own `limits` list states that a p-value
describes detectability at this sample size while ω² describes magnitude, and
that neither alone is practical importance.

## Three ways an F test is refused

An unreplicated or degenerate design has no error variance to test against.
Each case reports `UNAVAILABLE` with its own reason rather than emitting a
number:

1. **no residual degrees of freedom** — one observation per cell;
2. **no variation in the effect** — that term's sum of squares is zero;
3. **zero within-cell variance** — `F = (ss/df)/0` would claim infinite
   evidence from a small sample whose true residual variance is unknown.

The variance partition itself is still reported for an unreplicated design,
because a complete balanced layout supports it even when no error term does.
An unbalanced or incomplete design is refused outright by
`factorial_variance_decomposition` rather than analysed with an approximation.

## Multiple comparisons

Screening several pairs inflates the false-positive rate, so p-values are
corrected with the existing `stats.holm_bonferroni` (default) or
`stats.benjamini_hochberg`, or `none` if declared. The artifact records which
correction ran, over how many effect tests it was computed, and the corrected
value sits beside the raw one so both readings are visible.

## F distribution without scipy

scipy is not a project dependency, so `stats.f_sf` is implemented from the
regularized incomplete beta function via a modified Lentz continued fraction,
using `P(F > f) = I_{df2/(df2 + df1·f)}(df2/2, df1/2)`. It is pinned against
**twelve published critical values** at α = 0.05 and α = 0.01, including the
`df1 = 1` cases that equal `t(df2)²`. Maximum error 1.4e-5.

## Usage

```bash
apertus-eval-prep interactions \
  --rows reports/interactions/rows.json \
  --pairs 'prompt,backend;backend,quantization' \
  --correction holm_bonferroni \
  --n-boot 500 \
  --evidence-mode LOCAL_REAL_MODEL \
  --out reports/interactions/interactions.json
```

Input rows are `{<factor>: <level>, ..., "score": float}`. Rows that do not
declare both factors of a pair are excluded from that pair's analysis and
counted in `n_rows_without_both_factors` — they are never coerced into a
`"None"` level, which would invent a cell the design never ran.

## What this does not claim

These estimates describe the declared design and the evaluated configurations
only. An `UNAVAILABLE` interaction is a **design limitation, not evidence that
the factors do not interact** — distinguishing those two is the main thing this
module exists to get right. No causal claim is made, significance is never
presented as practical importance, and nothing here is production approval.
