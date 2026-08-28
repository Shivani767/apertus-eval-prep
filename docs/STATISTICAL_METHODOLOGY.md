# Statistical methodology

This document describes the statistical methods implemented in `src/apertus_eval_prep/stats.py` and used by `report.py`, `benchmark_report.py`, and `analysis.py`.

## Design principle

Statistics are chosen for **paired binary outcomes on fixed items**, not for decorative significance. Every test below assumes generative exact-match scoring on a frozen JSONL slice.

---

## Wilson score interval (accuracy)

**Function:** `wilson_interval(k, n, z=1.96)`

**Use:** Binomial proportion confidence interval for overall and per-task accuracy.

**When appropriate:** Any accuracy = k/n on n independent-ish Bernoulli trials. Preferred over normal approximation for small n (e.g. n=4 smoke, n=28 canary).

**Assumptions:** Items are treated as exchangeable; dependence from shared model/prompt is not modeled (conservative for ranking claims).

**Reported as:** `accuracy_ci95: [lo, hi]` in every run JSON and forest plots.

---

## McNemar's test (paired configurations)

**Function:** `mcnemar(correct_a, correct_b)`

**Use:** Same items, two configurations (control vs OFAT treatment). Tests whether disagreement rates differ.

**When appropriate:** Paired binary correctness on identical item IDs. Used for prompt_id, quantization, backend, seed cells vs same-model control.

**Assumptions:** Continuity-corrected χ² with 1 df; items are paired; only discordant pairs contribute.

**Not appropriate for:** Comparing different models on different random seeds without pairing; comparing unpaired runs.

**Interpretation:** Low p-value means scores move beyond sampling noise on **these items** — not necessarily a rank flip (check Kendall τ separately).

---

## Kendall's τ_b (ranking stability)

**Function:** `kendall_tau_b(ranks_a, ranks_b)`

**Use:** Rank correlation between control ranking and treatment ranking across ≥2 models.

**When appropriate:** OFAT cell has the same model set as control; ranks computed by competition ranking on overall accuracy (high is better).

**Assumptions:** At least two models in both rankings; ties handled by τ_b.

**Undefined when:** Only one model has a non-control factor level (e.g. SmolLM2-only prompt ablation) — report as `None`, not 0.

**Pair with:** `pairwise_reversals` — count of model pairs that swap order.

---

## CI-overlap ties

**Functions:** `cis_overlap`, `ci_aware_ties`

**Use:** If two models' Wilson intervals overlap, report as a **tie** even when point estimates differ (e.g. Phi 67.0% vs Qwen 64.4%).

**Rationale:** Point-estimate ranking without interval awareness overstates confidence on n=800 generative eval.

---

## CI width curve

**Function:** `ci_width_curve(correct_sequence)`

**Use:** Prefix Wilson interval as items accumulate — demonstrates why n=4 cannot rank models.

**Not a hypothesis test.** Educational / sensitivity analysis only.

---

## Derived metrics (`analysis.py`)

| Metric | Definition | Basis |
|---|---|---|
| `reasoning_gain` | acc_thinking − acc_non_thinking | Measured |
| `additional_tokens` | output_tokens_thinking − output_tokens_non_thinking | Measured |
| `reasoning_efficiency` | reasoning_gain / additional_tokens | Derived |
| `robustness_score` | 1 − (std/mean) across paraphrase variants | Derived |
| `accuracy_per_cost_estimated` | accuracy / USD_total | **Estimated** (YAML pricing) |
| `accuracy_per_second_measured` | accuracy / (e2e_ms_mean/1000) | Measured |
| `accuracy_delta` (quant) | acc_quant − acc_fp16 | Measured, paired McNemar when items match |

---

## Not implemented (and why)

| Method | Reason |
|---|---|
| Bootstrap CIs | Wilson adequate for proportions; bootstrap adds complexity without current need |
| ANOVA / mixed models | OFAT design intentionally avoids interaction estimation in v1 |
| LLM-as-judge significance | No LLM judge in harness |
| Bonferroni correction | Not applied — pre-registered cells are exploratory; p-values reported per comparison |

---

## References

- Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference.
- McNemar, Q. (1947). Note on the sampling error of the difference between correlated proportions.
- Kendall, M. G. (1938). A new measure of rank correlation.

See also: `docs/IMPLEMENTATION_AUDIT.md`, `paper/stability.md`.
