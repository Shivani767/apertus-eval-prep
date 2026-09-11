
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

## Fragility + variance (Phases 4, 6) — DERIVED from 31 measured rows

`fragility.py`: `score_sensitivity`, `rank_sensitivity`, `per_factor_sensitivity`,
`tie_fragility`, `sampling_spread`, `model_rank_summary` +
**provisional** `evaluation_fragility_index` (EFI) + `efi_ablation`.
EFI = 0.30*range + 0.35*(1-tau)/2 + 0.15*tie_frac + 0.20*CV, renormalized over
non-missing terms; tau None -> 0.5 flagged; weights renormalized (validated).
`variance.py`: descriptive one-way eta-squared + `decompose_variance` (marginal
shares, need not sum to 1 — OFAT confounds factors; no F/p at n=31) +
`interaction_screen` (UNAVAILABLE on OFAT, MEASURED only with crossed factorial
cells from `sweep.expand_factorial`).

Whole-matrix DERIVED snapshot (31 rows, code above — not a claim, a readout):
score range 0.466, std 0.137, CV 0.250; eta-squared model 0.893 vs factor 0.094
(model choice dominates because SmolLM2 ~0.37 vs others ~0.64-0.68; OFAT design
confounds this — read as description, not causal attribution).
