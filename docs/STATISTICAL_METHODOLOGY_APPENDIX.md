
## New research modules (this iteration)

All metrics below are documented with definitions, input/output contracts, and
synthetic-data tests in `tests/test_reliability.py`. They consume measured runs
only — no scores are invented.

### `result_schema.py` (Phase 1)

`STATUSES = MEASURED / SAMPLED / DERIVED / PENDING / UNAVAILABLE`.
`classify_row`: registry `ok` + greedy blob → MEASURED; + sampling blob → SAMPLED;
missing blob/row → PENDING (DERIVED/UNAVAILABLE assigned by callers).
`enrich_run`: read-only join to `{run_id, status, experiment_id, timestamp,
model{model_id, revision, tokenizer}, task{tasks, dataset_path/revision, n},
protocol{prompt*, fewshot, paraphrase, thinking, temperature/top_p/seed,
max_new_tokens, chat_template, backend(+version), quant, dtype, factor/level},
runtime{hardware, software, git_commit/dirty, device}, metric{accuracy, correct,
n, CI, per-task, latency, cost}, provenance{artifact_path, config_hash}, notes}`.
Missing → None, never 0. `validate_enriched`, `load_enriched_registry`,
`coverage` helpers. Live coverage: **25 MEASURED + 6 SAMPLED = 31 evidence**.

### `stability.py` (Phase 2)

`score_variance` (population), `score_std(sample?)`, `score_range`
(report with std, never alone), `coef_of_variation` (None when mean 0),
`bootstrap_ci_mean` (percentile, seeded/deterministic), `paired_difference`
(shared ids only, `n_dropped` reported), `cohens_h` (proportions),
`factor_sensitivity` (max pairwise |mean delta|, `empty_levels` listed, never imputed).

### `ranking.py` (Phase 3)

Reuses `stats.rank_high_is_better` (competition ranks, average-tie).
`spearman_rank_correlation` (Pearson of ranks, None when degenerate),
`pairwise_win_rates` (strict wins, pairwise-missing skipped, diagonal None),
`rank_distributions` (mean/var rank, P(#1), min/max, n_configs + n_skipped),
`bootstrap_ranking_stability` (resample configs, seeded; mean Kendall-tau vs
reference + P(any reversal)).

### `sweep.expand_factorial` (Phase 5)

Opt-in full-factorial over `axes` or explicit `only_combos` allow-list
(fractional/selected designs). `max_cells` budget raises instead of exploding.
Cells record `design: factorial` + `design_axes` for provenance. OFAT untouched.
