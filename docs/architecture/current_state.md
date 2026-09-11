# Current State: Architecture Audit (Phase 0)

Date: 2026-09-10. Method: direct inspection of every source module, test,
config, result artifact, and paper file in the repository at commit
`2763c74`. Every claim below was verified against the working tree; nothing
is aspirational. Components marked PARTIAL list exactly what is missing.

## 1. Current architecture

```
data/  (frozen slices + SOURCES.md, paraphrase_set, evalfrag seed)
  |   load_items(data_path, tasks, limit, paraphrase_id)
  v
configs/*.yaml --> load_config() --> RunConfig (dataclass, 22 fields,
  |                                  comparable_settings() = hash keys)
  | sweep.load_study() --> expand_ofat() / expand_factorial()
  |                        (cells = full RunConfig dicts + factor labels)
  v
run_eval(cfg, repo_root, checkpoint_path)          [the only runner]
  |   backends: hf.py / hf_load.py / vllm_backend.py
  |   prompting.py (prompt_id specs, fewshot, chat templates)
  |   scoring.py (per-item correct/normalized answer)
  |   checkpoint.py (.partial.jsonl resume)
  v
run JSON blob = {manifest{settings,git_commit,git_dirty,hardware,
                 packages,utc}, config_hash, overall{n,correct,accuracy,
                 accuracy_ci95}, per-task, items[{id,task,language,prompt,
                 generation,gold,predicted,correct,e2e_ms,ttft_ms,
                 num_new_tokens,tokens_per_sec,...}]}
  |
  v
results/registry[_paper].jsonl  (append-only, 31 rows: flat keys
  |                              config_hash,experiment_id,factor,
  |                              factor_level,git_commit,hardware,
  |                              model_id,overall,path,run_id,status,utc)
  v
analysis layer:  stats.py (Wilson, McNemar, Kendall tau-b, pairwise
  |               reversals, paired bootstrap diff CI, sign-flip
  |               permutation, Holm-BH, chi2 sf, ci-width curve)
  |               ranking.py (rank_high_is_better, rank distributions,
  |               bootstrap ranking stability, spearman, win rates)
  |               stability.py / variance.py / fragility.py (+EFI)
  |               reliability.py (ERS composite + ablation, provisional)
  |               adaptive.py (AdaptiveEvaluator, 3 strategies,
  |               compare_strategies over KNOWN score tables)
  v
reporting: report.py (stability.md, plots), analysis.py, benchmark_report,
           failures.py, pareto.py, profile.py, cost.py, metamorphic.py,
           reproduce.py (plan + --check deviation report), dashboard.py,
           paper tables via cli `paper` + Makefile
  v
paper/ (stability.md, _generated_tables.md, run_status.md, RELATED_WORK.md)
reports/ (dashboard, ers, failures, pareto, profile, ci_width, stability,
          stability_paper, validation - all generated from artifacts)
tests/ (24 files, 116 tests, synthetic fixtures, no network/GPU)
```

## 2. Existing components (verified)

| Area | Component | State |
|---|---|---|
| Config | `config.py` RunConfig + `comparable_settings()` | EXISTS, stable |
| Fingerprint | `registry.config_hash` (16-hex SHA over 16 keys; paraphrase/thinking only when non-default; intentionally stable for existing hashes) | EXISTS |
| Prompts | `prompts.py`, `prompting.py`, `configs/prompts/*.yaml`, `dump_prompts` | EXISTS |
| Manifests | per-run `manifest` (settings, git, hardware, packages, utc) + `manifest.py` | EXISTS |
| Runners | `run_eval.py` + `backends/{hf,vllm}_backend.py`, resume via `.partial.jsonl` | EXISTS (single runner, reused below) |
| Quantization | factor `none/int8/int4` (HF path), dtype field | EXISTS (HF-measured; vLLM 0.0 e2e placeholders known) |
| Profiling | `profile.py` (tok/s, e2e, TTFT per task/language), reports/profile | EXISTS |
| Cost | `cost.py` (MEASURED/DERIVED/UNAVAILABLE labels) | EXISTS |
| Statistics | `stats.py` incl. paired bootstrap CI, permutation, Holm/BH | EXISTS |
| Ranking | `ranking.py`, `stats.rank_high_is_better`, Kendall, Spearman | EXISTS |
| Reliability | `reliability.py` ERS + `ers_ablation` (PROVISIONAL, unvalidated) | EXISTS (hypothesis) |
| Fragility | `fragility.py` components + provisional EFI | EXISTS (hypothesis) |
| Variance | `variance.py` descriptive decomposition (OFAT-honest) | EXISTS |
| Adaptive | `adaptive.py` select/observe loop, random/uncertainty/max_disagreement, `compare_strategies` (known tables only) | EXISTS (not yet wired to real execution) |
| Reproduction | `reproduce.py` plan + `verify_reproduction` (hash recompute, accuracy, git) | EXISTS; `--execute` rerun MISSING |
| Failures | `failures.py` 5-category taxonomy + CLI | EXISTS |
| Metamorphic | `metamorphic.py` transforms + `data/evalfrag/evalfrag_seed.jsonl` (12 rows, all observed PENDING) | EXISTS |
| Pareto | `pareto.py` quality/latency front | EXISTS |
| Dashboard | `dashboard.py` coverage/ERS/verify/failures -> md+json | EXISTS |
| Paper | `report.py` tables + `make paper`/`figures` (markdown only) | EXISTS |
| Tests | 24 files, 116 passing, fixtures + tiny study.yaml | EXISTS |
| Docker | Dockerfile | EXISTS |
| CI | - | **MISSING** (no .github/) |

## 3. Reusable components (integration targets, not rewrites)

- `run_eval(cfg, ...)` — the single runner; planner output must be
  `RunConfig`-shaped dicts so execution needs no new path.
- `registry.config_hash` — canonical identity; new experiment records MUST
  reuse it (never a second hash function).
- `expand_ofat` / `expand_factorial` — already produce the candidate pool;
  the planner wraps them plus explicit selection/held-out state.
- `AdaptiveEvaluator` (select/observe/stop, `selection_reason` in
  candidates) — wire its `select()` to real registry rows instead of
  synthetic tables; do not replace the strategies.
- `reproduce.verify_reproduction` — extend with `--execute` (rerun via the
  same runner into `results/reproductions/`), keep existing checks.
- `stats.py` paired-bootstrap/permutation/Holm-BH — sufficient for claim
  tests; no new stats module.
- `dashboard.py`, `report.py`, Makefile targets — extend inputs; keep output
  contracts (md + json sidecars).

## 4. Missing components

| Gap | Consequence | Planned module |
|---|---|---|
| Dataset/model registries (id, revision, license, sha256 fingerprint, schema version) | `SOURCES.md` is prose only; items carry no dataset revision; models carry `revision: None` | `catalog.py` + `data/catalog/*.jsonl` |
| Experiment planner (`apertus plan`) | sweep expands cells but there is no candidate/selected/completed/failed/held-out state file | `planner.py` + `results/plans/<study>.json` |
| Held-out isolation | nothing marks cells off-limits to adaptive selection | planner state (held-out partition excluded from adaptive observation) |
| `reproduce --execute` | verification is static; no true rerun comparison | extend `reproduce.py` (same runner, deterministic seed) |
| ERS validation experiment | ERS is an unvalidated hypothesis; no calibration evidence | `ers_validation` analysis + doc |
| Cross-experiment query index | JSONL scan only; "which cells flipped rankings" needs O(n) scan | optional SQLite/DuckDB index (JSONL stays canonical) |
| Claims registry | paper numbers not yet linked to run IDs/analyses | `paper/claims/*.json` + generator |
| Research log | decisions live in commit messages only | `docs/research_log/` templates |
| CI | tests only run locally | `.github/workflows/ci.yml` |
| Multilingual expansion beyond measured items | mgsm items exist with `language`; no Indic dataset acquisition/infra | documented roadmap; no fabricated data |

## 5. Duplicate / overlapping components (known)

- CI-separation logic: `reliability._ci_separation` re-implements the
  overlap test already in `stats.ci_aware_ties` (documented trade-off:
  matrix input vs run-list input; candidate for consolidation).
- Spread/sensitivity: `stability.factor_sensitivity`, `fragility`
  components, and ERS `config_stability` compute related quantities from
  grouped scores; definitions differ (max delta vs std ratio) and are kept
  separate on purpose until ERS validation decides.
- `report.py` vs `analysis.py` vs `benchmark_report` produce overlapping
  tables from the registry (historical layers; consolidation deferred to
  avoid breaking existing paper outputs).

## 6. Integration gaps

1. No planner → runner → registry → adaptive loop: `compare_strategies`
   replays KNOWN score tables; it has never selected a real run.
2. Registry rows carry `overall` aggregates; aggregate-vs-items
   consistency is checked only in `reproduce.verify_reproduction`, not at
   write time.
3. `model_revision`/`dataset_revision` are absent end-to-end, so a
   reproduction cannot currently pin what was actually downloaded.
4. Held-out/confirmatory split does not exist; adaptive decisions and final
   evaluation would share the same cells today.
5. CI absence means registry-consistency and hash checks run only when a
   developer remembers.

## 7. Proposed final architecture (incremental, additive)

```
catalog.py        dataset/model records + sha256 fingerprints (new)
planner.py        candidate pool (reuse expand_*) -> plan state file with
                  candidate/selected/completed/failed/held-out + reasons
cli: plan         deterministic manifest generation (same hash identity)
runner loop       plan -> run_eval (existing) -> run JSON -> registry row
                  -> adaptive.observe -> next select -> stop decision log
reproduce --exec  rerun from manifest.settings via run_eval; compare
                  predictions/metrics; deviation report (extends existing)
ers_validation    component-vs-outcome calibration on real matrices; doc
index (optional)  SQLite/DuckDB mirror of registry+items for queries
claims            claim -> evidence (run_ids, analysis, figure) -> status
ci.yml            pytest + CLI smoke + registry/hash/artifact consistency
```

Principles: JSONL registry stays canonical; one runner; one hash; planner
state is the only place adaptive may read; every new artifact carries
MEASURED/DERIVED labels; pending work is generated as manifests marked
NOT RUN, never as numbers.
