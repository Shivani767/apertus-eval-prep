# Existing-evidence analysis (DERIVED)

Generated 2026-09-28T13:36:11.939573+00:00 · seed 0 · registry `/Users/shivanibhandari/Downloads/projects/ETH : EPFL Apertus /apertus-eval-prep/results/registry_paper.jsonl`

No model was executed and no committed artifact was modified. Every value is derived from files already in this repository.

## Chat-template discordance (paired, one knob changed)

- shared items: 28 (unmatched: 0)
- templated-only correct: 6; none-only correct: 1
- exact sign test p = 0.125

| task | n | templated only | none only | both right | both wrong |
|---|---:|---:|---:|---:|---:|
| arc_easy | 8 | 3 | 0 | 5 | 0 |
| gsm8k | 8 | 0 | 0 | 2 | 6 |
| multilingual | 8 | 2 | 0 | 5 | 1 |
| template_canary | 4 | 1 | 1 | 2 | 0 |

## Factorial screen

| design | status | complete | balanced | reason |
|---|---|---|---|---|
| model_id×factor | UNAVAILABLE | False | False | ANOVA requires a complete, balanced design; rerun as a balanced factorial (see interaction.interaction_design) |

## Leave-one-model-out (low-power probe; three models meet the minimum of three)

models: 3, configurations: 11, budgets dropped as too large: []

| budget | hidden | visible | in-distribution decision acc | hidden std |
|---:|---:|---:|---:|---:|
| 2 | 0 | 2 | 1.000 | 0.0497 |
| 4 | 0 | 2 | 1.000 | 0.0497 |
| 6 | 2 | 2 | 1.000 | 0.0443 |
| 8 | 2 | 2 | 1.000 | 0.0443 |

