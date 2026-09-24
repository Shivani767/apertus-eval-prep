# Research Gap Analysis

**Date:** 2026-12-09
**Base commit:** `6b83cd0` (working tree clean before this analysis)
**Method:** full source inspection of `src/apertus_eval_prep/`, `tests/`, `configs/`,
`results/`, `reports/`, `paper/`, `frontend/`, `docs/`; test-suite baseline
(135 passed, 0 failed, 0 warnings, 2.60 s); registry audit
(`results/registry_paper.jsonl`, 31/34 T4 cells `status=ok`).

Status legend:

| Status | Meaning |
|---|---|
| **FULLY IMPLEMENTED** | Code exists, tests pass, used by a command, produces an artifact |
| **PARTIALLY IMPLEMENTED** | Core path works; a scientifically required part is missing |
| **DOCUMENTED ONLY** | Described in docs/paper but no working code path |
| **MISSING** | Not implemented |

---

## A. Existing capabilities (verified)

| Capability | Status | Primary files | Test coverage |
|---|---|---|---|
| Configuration-driven experiments (YAML → RunConfig) | FULLY | `config.py`, `configs/`, `sweep.load_study` | `test_sweep.py` |
| HF / vLLM backends + quantization | FULLY | `backends/{hf,vllm}.py`, `run_eval.py` | `test_hf_backend.py` |
| OFAT sweep with resume + registry dedup | FULLY | `sweep.expand_ofat/execute_sweep`, `checkpoint.py` | `test_sweep.py`, `test_checkpoint.py` |
| Result registry + config hashing | FULLY | `registry.py` | `test_sweep.py` |
| Status model (MEASURED/SAMPLED/DERIVED/PENDING/UNAVAILABLE) | FULLY | `result_schema.py` | `test_reliability.py` |
| Statistical inference: Wilson, McNemar, Kendall τ_b, reversals, CI ties, paired bootstrap CI, sign-flip permutation, Holm/BH | FULLY | `stats.py` | `test_stats.py` |
| Ranking analysis: Spearman, win rates, rank distributions, bootstrap rank stability | FULLY | `ranking.py` | `test_reliability.py` |
| Stability metrics: variance/std/range/CV, bootstrap CI, Cohen's h, factor sensitivity | FULLY | `stability.py` | `test_reliability.py` |
| Fragility components + provisional EFI + ablation | FULLY | `fragility.py` | `test_fragility.py` |
| Variance: one-way η², OFAT-safe interaction *screen* | PARTIAL (descriptive only, no factorial decomposition) | `variance.py` | `test_fragility.py` |
| ERS composite (provisional) + ablation | PARTIAL (never validated against a hidden target) | `reliability.py` | `test_ers.py` |
| Adaptive evaluation: 3 strategies + replay harness over KNOWN tables | PARTIAL (no Apertus-R, no OFAT/LHS baselines, no budget curves, no cost-aware utility) | `adaptive.py` | `test_adaptive.py` |
| Cost tracking with quality labels + budget_curve sink | FULLY (no real (cost, confidence) observations yet) | `cost.py` | `test_cost.py` |
| Pareto frontier | FULLY | `pareto.py`, `analysis.py` | `test_pareto.py` |
| Metamorphic evaluation + EvalFrag seed (PENDING measurements) | FULLY | `metamorphic.py` | `test_metamorphic.py` |
| Failure taxonomy (per-item, 5 classes) | PARTIAL (no change-flux atlas / 12-class taxonomy / case studies) | `failures.py` | `test_failures.py` |
| Reproducibility: plan + deviation verification | FULLY | `reproduce.py` | `test_reproduce*.py` |
| Experiment runner + research report generator | FULLY | `experiment_runner.py`, `report_generation.py` | `test_experiment_runner.py` |
| Dashboard / paper tables / figures from registry | FULLY | `report.py`, `site.py`, `dashboard.py` | `test_report.py`, `test_site.py` |
| Dataset fingerprinting + model coverage catalog | FULLY | `catalog.py` | `test_catalog.py` |
| Paper artifacts (markdown) | PARTIAL (no LaTeX, no reproducible figure scripts) | `paper/` | — |
| Frontend (12-page dashboard, deterministic site.json) | FULLY | `frontend/`, `site.py` | `test_site.py` |
| Tests | 135 passed | `tests/` | — |
---

## B. Missing scientific capabilities

Ranked by value to the central research question
("can we trust an LLM model comparison when reasonable evaluation
conditions change?").

1. **Held-out configuration splitting (leakage-free train/holdout).** Nothing
   marks configurations off-limits to fitting the reliability estimator.
   `docs/architecture/current_state.md` records this gap explicitly.
2. **ERS / reliability-estimator validation against held-out configurations.**
   ERS is computed and labelled provisional, but no calibration (Brier,
   log-loss, ECE, AUROC, CI coverage) against `C_test` exists. The prediction
   target of ERS is not formalized.
3. **Decision reliability** `P(A > B | C ~ P(C))` — the third stability type
   (score / ranking / decision) is not defined or estimated.
4. **Factorial variance decomposition** (main effects + interaction +
   residual with diagnostics and uncertainty) for crossed designs. Current
   `variance.py` is a one-way descriptive screen only.
5. **Interaction-study experiment subsystem** with balanced / fractional
   designs, deterministic generation, and registry-compatible provenance.
   `sweep.expand_factorial` is a raw Cartesian + explicit allow-list; it does
   not implement balanced subset selection (e.g. 2^k-p fractional / random
   balanced under seed), nor a dedicated experiment type recording the
   design axes in provenance.
6. **Apertus-R reliability-aware acquisition** (utility = expected
   uncertainty reduction / evaluation cost) and fair budget comparisons
   (Random / OFAT / Apertus-R and optional LHS) across budgets with
   mean + CI. `compare_strategies` today returns a single-budget point
   estimate per strategy with no CIs.
7. **Budget-curve study** (5 / 10 / 20 / 40 / 80 / full) with
   RankingRecovery, PairwiseDecisionAccuracy, ScoreError, ReliabilityError,
   KendallTau, EvaluationCost, repeated stochastic sampling.
8. **Generalization experiments** — held-out configurations *and* held-out
   model(s) / task(s), separating in-distribution from out-of-distribution
   reliability estimation.
9. **Failure atlas** — change-flux classification between a control and a
   variant run over the requested 12-class taxonomy, machine-readable records,
   and representative case studies.
10. **Provenance expansion** — prompt hash, chat-template hash, model /
    dataset revision, hardware/runtime; explicit `UNAVAILABLE` labels.
11. **LaTeX paper artifact** (`main.tex`, `references.bib`, `figures/`,
    `tables/`, `appendix/`) with a figure/tables generation script that is
    reproducible from registered results and smoke experiments.
12. **README as a research artifact** (research question → contributions →
    method → setup → results → limitations → artifact).
13. **Integrity audit + readiness report** (`docs/research_integrity_audit.md`,
    `reports/research_readiness_report.md`).
14. **Tests for every new component** incl. pathological cases (ties, missing
    measurements, single configuration/model, zero variance, NaN, failed
    evaluation, duplicated configuration, identical/opposite rankings).
| Documentation | RESEARCH_PLAN, RESEARCH_AUDIT, IMPLEMENTATION_AUDIT, STATISTICAL_METHODOLOGY(+appendix), EVALUATION_COST, VALIDATION, METAMORPHIC_EVAL, architecture/current_state | `docs/` | — |
---

## C. Existing modules that can be extended

| Module | What exists | Extension for this research system |
|---|---|---|
| `sweep.py` | `expand_ofat`, raw `expand_factorial`, `execute_sweep` | re-used cell builders + runner path for interaction studies |
| `variance.py` | one-way η², interaction screen | factorial ANOVA decomposition, bootstrap CIs, diagnostics |
| `reliability.py` | ERS + ablation | decision reliability + stability tri-type profile; ERS target formalization |
| `adaptive.py` | 3 strategies, single-budget replay | Apertus-R strategy, OFAT/LHS baselines, multi-budget curves with CI |
| `failures.py` | per-item 5-class taxonomy | change-flux failure atlas (12 classes, machine-readable, case studies) |
| `registry.py` / `result_schema.py` | hash + enriched view | formal configuration record + full provenance summary |
| `cli.py` | many subcommands | `interaction`, `heldout`, `budget`, `variance`, `atlas`, `provenance`, `paper-tex` |
| `config.py` | RunConfig | decoding knobs needed for Prompt × Decoding interaction studies |
| `site.py` / dashboard labels | MEASURED/DERIVED/PENDING | add PREDICTED / HELD-OUT / provisional labels |
| `report_generation.py` | report builder | sections for interactions, decision reliability, budget curves |

---

## D. Proposed implementation mapping

| Phase (task) | New/changed file | Existing reused |
|---|---|---|
| 1 — formal model | `docs/research_formulation.md`, `src/.../configuration.py` | `registry.config_hash` |
| 2 — interaction studies | `src/.../interaction.py`, `configs/experiments/interaction_*.yaml`, CLI | `sweep._base_cell/cell_to_run_config/run_id_for/execute_sweep`, `registry` |
| 3 — variance decomposition | extend `variance.py` | `stats` |
| 4 — three stability types | extend `reliability.py` | `ranking`, `stats`, `stability` |
| 5 — ERS formalization + validation | `src/.../heldout.py` (train/holdout), `src/.../ers_validation.py` | `reliability`, `registry`, `result_schema` |
| 6 — held-out experiment | `heldout.py` + CLI `--budget` | metric reuse from `ranking` |
| 7 — Apertus-R | extend `adaptive.py` | `cost` quality labels for cost term |
| 8 — budget curves | extend `adaptive.py` + `scripts/make_paper_figures.py` | `stats` bootstrap |
| 9 — generalization | `src/.../generalization.py` (new) | `heldout.split`, `ers_validation` |
| 10 — failure atlas | `src/.../failure_atlas.py` (new) | `failures.classify_item` |
| 12 — provenance | `src/.../provenance.py` (new) | `manifest`, `catalog`, `registry` |
| 13–14 — paper | `paper/main.tex`, `paper/references.bib`, `paper/{figures,tables,appendix}/`, `scripts/make_paper_figures.py` | `report.paper_tables`, registry JSON |
| 16 — README | `README.md` rewrite | — |
| 17 — frontend | label additions in `site.py`; minimal `Overview.tsx` wording | existing site pipeline |
| 18 — tests | new `tests/test_*.py` files | synthetic fixtures pattern |
| 19 — audit | `docs/research_integrity_audit.md` | — |
| 20 — validation | `reports/research_readiness_report.md`, smoke runs | CLI smoke configs |

---

## E. Risks / methodological limitations

1. **No GPU in this environment.** Interaction, held-out, and budget
   experiments cannot be run on real T4 hardware here. Mitigation: every new
   experiment path ships with a **SMOKE profile** (tiny deterministic
   synthetic "measurements" used only to validate the analysis path, never
   claimed as experimental evidence) and a documented command to scale to
   real GPU runs. Real-data versions of analyses that CAN be computed from
   the committed 31-cell registry (variance screen, ERS, ranking instability)
   are computed from actual artifacts.
2. **Small observed registry (31 cells, 4 models, 1 GPU, 800 items/cell).**
   Any interaction claim from real data is restricted to the factor pairs the
   registry actually crosses (e.g. prompt × backend). Everything else is
   `PENDING` and reported as such.
3. **ANOVA assumptions.** The factorial decomposition is only valid for
   balanced, complete designs with independent observations. The implementation
   reports balance/completeness diagnostics and refuses (returns
   `UNAVAILABLE`) rather than forcing an ANOVA on unbalanced data — mirroring
   the existing `interaction_screen` policy.
4. **ERS is not ground truth.** Its validity is claimed only for the evaluated
   configuration distribution; the validation experiment is the arbiter, not
   the composite itself.
5. **External validity.** Models, benchmarks, hardware, prompts, and decoders
   covered here are a small subset of the space; all conclusions are scoped to
   the evaluated distribution.
6. **Greedy-decoding seeds.** Seeds under greedy decoding are near no-ops for
   score variation; decisions should not lean on seed sensitivity alone.
7. **Pairwise P(A > B) estimates** treat observed configurations as an i.i.d.
   sample from P(C); that is a modeling assumption, documented per output.
8. **Evaluation cost** is only recorded as DERIVED `est_total_s` where
   measured; the cost term in Apertus-R is a documented proxy until real
   metered cost exists.