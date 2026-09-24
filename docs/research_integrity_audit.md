# Research Integrity Audit

Scope: leakage, fairness, and traceability of the research subsystems added
during the uncertainty-of-comparison evolution (held-out reliability,
interaction studies, adaptive evaluation, budget curves, generalization).

Status: performed on the code state passing the full test suite (231 tests).

## 1. Held-out configurations are never used for fitting

- `heldout.split_config_keys` produces a deterministic, stored partition
  (`train` / `heldout` key lists + `leakage_guard` metadata). The split is
  metadata, not a re-derivation from results.
- `heldout.pairwise_estimates` fits `p_hat` strictly on the train partition;
  `test_holdout_mutation_cannot_change_p_hat` proves mutating holdout scores
  cannot move any fit, while `test_train_mutation_changes_p_hat` proves the
  control direction works.
- Test coverage: `tests/test_research_integrity.py`
  (`test_partitions_never_overlap_any_budget_seed` sweeps budgets x seeds).

## 2. Test results do not influence configuration selection

- Adaptive selection (`AdaptiveEvaluator.select_next`) observes only scores
  passed to `observe` before the selection step.
- `test_apertus_r_selection_is_independent_of_future_scores` constructs two
  worlds identical except for one future score and proves the selection
  sequence is identical until that score is actually observed.

## 3. Adaptive selection uses only information available at that point

- Same test as above; additionally `test_budget_curves_*` replay metrics are
  computed from the measurement log only (`n_measured` == budget is recorded
  as provenance of evidence used).

## 4. Model selection does not use future results

- Budget-curve replays estimate rankings only from measured cells
  (`_replay_metrics`); unmeasured pairs yield `None`, never an imputed value
  (`test_replay_metrics_small_budget_may_measure_few_models`).

## 5. Benchmark answers are not leaked

- This codebase contains no benchmark answer keys; scores enter the analysis
  layer only through the registry / score tables. Prompt variants are keyed
  by `prompt_id` and isolated at the RunConfig level (see
  `interaction.FACTOR_FIELDS` and `_apply_level`).

## 6. Preprocessing consistency

- All research metrics consume the same score table representation; no
  metric re-scales or re-derives scores internally. Variance decomposition
  refuses unbalanced/incomplete designs rather than imputing
  (`factorial_variance_decomposition` guards, tested in
  `tests/test_pathological.py`).

## 7. Seeds and reproducibility

- All stochastic stages take explicit seeds: `split_config_keys(seed)`,
  `balanced_select(seed)`, `_bootstrap_p_ci(seed)`, per-budget derived seeds
  (`budget_seed`). Determinism is test-enforced
  (`test_interaction_study_deterministic`,
  `test_budget_curves_deterministic`, `test_selection_sequence_deterministic...`).

## 8. Reported statistics are generated from raw results

- `test_budget_curve_means_match_recomputed_replays` recomputes a curve mean
  independently from per-rep replays and matches it to 1e-9.
- `scripts/research_smoke.py` writes all headline numbers by reading the
  produced artifacts, not by hand-typing.

## 9. Figures from registered results

- Paper figures/tables are generated from registry/report outputs by
  generation scripts (paper/run_status.md tracks which are registry-backed).
- The synthetic smoke run is labeled `data: synthetic (validation only)` in
  its output JSON and must never be cited as experimental evidence.

## 10. Known residual risks

- Tie handling: pairwise decisions exclude tied configs (documented in
  `heldout.pairwise_estimates`); calibration probabilities therefore describe
  decidable configs only. Any external consumer must respect `n_ties_*`.
- Leave-one-model-out is descriptive OOD reporting, not OOD prediction
  (labeled as such in the output).
- ERS validity is bounded to the evaluated configuration distribution; no
  universal-validity claim is made anywhere in the modules.
