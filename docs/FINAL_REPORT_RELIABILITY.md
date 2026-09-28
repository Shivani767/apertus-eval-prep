# Final report: measurement reliability under evaluation configuration

Generated against `36ae8dd`. Every number below was produced by running the
committed code; nothing here is asserted from intent.

---

## 1. What changed

Eight new modules, six new CLI commands, four new documents, 216 new tests.

| Area | Added |
|---|---|
| Decision stability | `decision.py` (544 lines) — does a declared selection policy pick the same option everywhere? |
| Ranking stability | `ranking.py` extended — reversal rate, top-1, top-k set stability |
| Factorial interaction | `factorial.py` (265), `stats.f_sf`, `variance._f_tests` |
| Agent reliability | `agent_reliability.py` (478) — coverage, comparison, regression gates |
| Evaluation sensitivity | `sensitivity.py` (216) — ESI against a declared scale |
| LLM-judge reliability | `judge.py` (302) — instrument characterisation, never ground truth |
| Metamorphic relations | `metamorphic.relation_report` — declared vs observed |
| Multilingual track | `multilingual.py` (197) — en / hi / hinglish |
| Deployment decisions | `deployment_decision.py` (183) — quality × latency × cost × **memory** |
| Dashboard | `dashboard_sections.py` (272) — six artifact-backed sections |

---

## 2. Research contribution

The thesis is that a benchmark score is a measurement produced under a
configuration, not a property of a model. These additions let that thesis be
**checked** rather than asserted, each closing a specific way a measurement
study can produce a confident wrong answer.

- **Score, ranking and decision stability are now separate measurements.** A
  ranking can churn while the selected model never changes, and a ranking can
  look stable while the decision flips inside the noise band.
- **An OFAT design cannot measure interactions, and now says so.** Feeding the
  committed `registry_paper.jsonl` shape to `interactions` returns
  `insufficient_design`, 0 effects tested, and *"no requested pair could be
  decomposed"* — not "no interaction found". Conflating unmeasured with absent
  is the most common way an interaction study reports backwards.
- **Unmeasured is never zero, at every layer.** A missing objective is
  `insufficient_evidence`; a missing metric is `not_comparable`; a missing
  memory figure excludes the option; a missing dashboard artifact renders
  `not_generated`. A fake zero would pass a cost ceiling and win the min-cost
  objective outright.
- **The ESI is dimensionless and says so.** Without a declared uncertainty
  scale it is `null` with a reason, not computed from a convenient default.
- **A judge is an instrument.** Position bias is measured from genuine swap
  pairs; single-order data reports that it *cannot* see bias rather than
  inferring it.
- **Code-switching is expected to move the score.** `hinglish` declares
  `not_invariant`, so a real code-switching effect is a measurement. Scoring it
  as a metamorphic violation would report the finding backwards.

---

## 3. Engineering contribution

Nine new typed modules reusing existing infrastructure rather than duplicating
it. Selection delegates to `metrics.pareto.select_configurations`; ranking reuses
`stats.pairwise_reversals` / `kendall_tau_b` / `rank_high_is_better`; factorial
reuses `interaction.py` and `variance.factorial_variance_decomposition`; gates
follow `release/gates.py`. Five conventions are now shared across the layer:

1. The denominator is stated in the artifact.
2. Missing is never zero.
3. Refuse rather than approximate — `insufficient_design` with a reason.
4. No causal language; factor attribution carries `causal_claim: false` and a
   design-quality label.
5. Evidence tier is declared (`--evidence-mode`, default `UNKNOWN`), never
   inferred upward.

**No new dependency.** `stats.f_sf` implements the F survival function from the
regularized incomplete beta via a modified Lentz continued fraction, because
scipy is not installed. Verified against **12 published critical values** at
α = 0.05 and 0.01, max error 1.4e-5.

---

## 4. New CLI commands

```bash
apertus-eval-prep decision-stability  --configurations <json> --policy <yaml>
apertus-eval-prep ranking-stability   --matrix <json> --k N
apertus-eval-prep sensitivity         --rows <json> --factors a,b --wilson-scale ACC N
apertus-eval-prep interactions        --rows <json> --pairs 'a,b;c,d' --correction holm_bonferroni
apertus-eval-prep agent-regression    --baseline <dir> --candidate <dir> --policy <yaml>
apertus-eval-prep scenario-coverage   --scenarios <yaml> --outcomes <json>
```

Each follows the existing `heldout` / `ers` naming, accepts `--evidence-mode`
from the canonical list defaulting to `UNKNOWN`, and runs offline with sockets
blocked.

---

## 5. New metrics and definitions

| Metric | Definition |
|---|---|
| `decision_stability` | same_decision / valid_configurations (denominator in artifact) |
| `stability_allowing_ties` | (same + tie_with_baseline) / valid — reported separately, never merged |
| `rank_reversal_rate` | changed best-first orderings / valid perturbations |
| `top_k_set_stability` | unchanged top-k **set** / valid perturbations |
| `mean_kendall_tau`, `mean_pairwise_inversion_rate` | ordering agreement, kept separate |
| `esi` | absolute_delta / **declared** uncertainty scale; dimensionless |
| `metamorphic_consistency` | relation_held / measured pairs |
| `count_coverage` / `execution_coverage` / `success_rate_of_executed` | declared / executed / succeeded — never merged |
| `rubric_disagreement`, `position_flipped` | judge instrument instability |
| `decision_completeness` | complete / partial — were all decisive objectives measured? |
| `F`, `p_value`, `p_value_corrected`, `omega2_pct` | factorial main effects and interaction |

**Deliberately absent:** any composite stability score, any causal claim, any
language ranking, any production-approval language.

---

## 6. Tests

```
408 passed  (before this work)
624 passed  (after)   — 216 new across 14 commits
```

| File | Tests |
|---|---|
| `test_judge_reliability.py` | 58 |
| `test_agent_reliability.py` | 38 |
| `test_decision_stability.py` | 34 |
| `test_factorial_f_tests.py` | 27 |
| `test_factorial_analysis.py` | 23 |
| `test_ranking_stability.py` | 19 |
| `test_sensitivity_and_dashboard.py` | 17 |

Verified: mock path runs with sockets blocked; existing CLI unchanged; no
secrets; no generated junk; `py_compile` clean (the repo configures no linter).

---

## 7. Files changed

**src** — `decision.py`, `sensitivity.py`, `factorial.py`,
`agent_reliability.py`, `judge.py`, `multilingual.py`,
`deployment_decision.py`, `dashboard_sections.py`; extended `ranking.py`,
`metamorphic.py`, `variance.py`, `stats.py`, `site.py`, `cli.py`

**tests** — 7 new files; **0 existing tests modified or deleted**

**configs** — `decision_policies/example.yaml`, `agent/regression_policy.yaml`,
`agent/scenarios.yaml`

**docs** — `DECISION_STABILITY.md`, `RANKING_STABILITY.md`,
`FACTORIAL_EXPERIMENTS.md`, `AGENT_EVALUATION.md`; extended `README.md`,
`ARCHITECTURE.md`, `EXTENDING_THE_PLATFORM.md`

**frontend** — the site export gained `analysis_sections`; six sections project
committed artifacts. **No experimental number is written into frontend code.**

---

## 8. Example mock workflow

```bash
# 1. configuration: a declared policy
cat configs/agent/regression_policy.yaml

# 2. experiment: two finished agent runs
apertus-eval-prep platform-episode --config configs/platform_phase3_agent.yaml --out /tmp/base

# 3. analysis + policy gate
apertus-eval-prep agent-regression --baseline /tmp/base/<run> --candidate /tmp/cand/<run> \
  --policy configs/agent/regression_policy.yaml --evidence-mode MOCK \
  --out reports/agent_regression/agent_regression.json

# 4. artifact -> dashboard
apertus-eval-prep site --registry results/registry_paper.jsonl --out reports/site
```

Observed on the live run: `gate_status: INCONCLUSIVE` because
`unsafe_action_rate` has a zero baseline, so a `maximum_relative_increase` rule
is undefined for it. A measured breach reads `FAIL`; a missing metric reads
`INCONCLUSIVE` and can never pass.

---

## 9. Research limitations

This implementation **does not** prove:

- That any model is better, safer, or production-ready.
- That chat templates cause any observed score change. The committed finding is
  directional, p = 0.125, n = 28 — **not significant**.
- Any causal attribution. Every reversal cause is an association carrying a
  design-quality label.
- That agent regression gates generalise beyond the evaluated scenarios. The
  comparison now **verifies** that both runs share a dataset signature and
  refuses to emit any delta when they do not.
- Any language ranking or code-switching finding — no items have been run in
  Hindi or Hinglish.
- Leave-one-model-out generalization: 4 models is a low-power probe, and the
  artifact says so.
- Any interaction effect. **None have been measured** — the committed registry
  is OFAT.

Structural gaps that remain open:

- The six dashboard sections all currently render `not_generated`; no analysis
  artifacts are committed, so the UI shows no data until the commands are run.
- `judge.py`, `multilingual.py` and `deployment_decision.py` are libraries with
  no CLI or dashboard surface yet.
- Human-review agreement/adjudication is not wired into the new artifact
  conventions.
- **Apertus/InferLite interoperability is not implemented.** Neither appears
  anywhere in the repository, so an interop layer would mean inventing an API
  contract against a guess — exactly the fabrication this project exists to
  avoid.

---

## 10. Suggested next real-model experiment

**Does the chat-template effect replicate as an interaction rather than a main
effect?**

*Why this one.* The committed finding is a main effect measured under OFAT:
6 templated-only vs 1 raw-only correct out of 28, sign test p = 0.125. It is
directional and not significant. The framework now exists to ask the sharper
question, and this is the highest-value question the repository is already
equipped to answer.

*Hypothesis, declared before running.* H₀: prompt-format level and model
identity do not interact; the effect is additive. H₁: they do — some models are
prompt-sensitive and others are not.

*Design.* A 2 × 3 factorial, deliberately not OFAT:

- factor `prompt`: `tokenizer` vs `none` (the level that produced the effect)
- factor `model`: three instruction-tuned models spanning the size range
- balanced, ≥ 3 seeds per cell → 36 runs, inside the `interaction.py` budget

*Why a factorial is required.* Under OFAT the `prompt=none, model=B` cell may
never have run. `interactions` would then return `insufficient_design` — the
correct, and already-tested, behaviour.

*Protocol.* Frozen eval slice, pinned model revisions, `HF_TOKEN` in Colab
secrets, chat-template fix already at `ead7db2`. Use
`interaction_design(..., design="full")` and seed the runs.

*What it would and would not show.* If the interaction term is large with ω²
comparable to the main effects, the claim sharpens to "the template effect is
model-specific" — a genuinely new and more useful finding. If it is small, the
honest result is that the effect is additive and p = 0.125 stands as
underpowered. **Neither outcome is known in advance and the result must be
reported whichever way it comes out.** No number for this experiment appears
anywhere in this repository.
