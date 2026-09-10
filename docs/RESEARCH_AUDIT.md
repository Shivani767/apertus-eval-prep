# Repository audit (2026-09-11) — "When can we trust an LLM benchmark?"

Date: 2026-09-11. Base: `cb0c4c7`. Tests: **58 passed**.
Registry: `results/registry_paper.jsonl` **31/34 T4 cells**; missing = Phi sampled x3.

## 1. Package structure

- `cli.py` + `__main__.py`: entry points (`eval, sweep, report, paper, ...`).
- `config.py`: `RunConfig` dataclass + YAML validation.
- `sweep.py`: OFAT `expand_ofat` + `execute_sweep` + resume.
- `run_eval.py`: eval loop (items -> backend -> scoring -> payload).
- `backends/hf.py, vllm_backend.py, hf_load.py`.
- `prompting.py / prompts.py / templates.py`: prompt + frozen JSONL items.
- `scoring.py`: extractors + task/language/latency/cost summaries.
- `manifest.py`: utc + git commit/dirty + packages + hardware + settings.
- `registry.py`: sha256[:16] `config_hash` + load/append/completed.
- `checkpoint.py`: `.partial.jsonl` resume.
- `stats.py`: wilson, mcnemar, kendall_tau_b, ranks, reversals, CI ties.
- `analysis.py`: thinking/multilingual/paraphrase/quant/cost/pareto/OFAT.
- `report.py`: `ranking_table`, McNemar pairing, paper tables, figures.
- `compare.py / benchmark_report.py / reproduce.py / dump_prompts.py`.

## 2. Config + result model (current)

`RunConfig`: model/backend/template/quant/temperature/top_p/seed/prompt_id/
paraphrase_id/thinking_mode/data/tasks/limit/cost. `comparable_settings()` is the
incomparability fingerprint; `config_hash` omits `paraphrase_id=orig` and falsy
`thinking_mode` so paper hashes stay stable
(`test_paper_control_hash_stable_if_paraphrase_default`).

Run JSON: `manifest{utc, git_commit, dirty, packages, hardware, settings}`,
`incomparability[]`, `tasks{per-task + overall{n,correct,accuracy,accuracy_ci95}}`,
`latency, language, items[], cost?`.
Registry row: `run_id, config_hash, experiment_id, model_id, factor, factor_level,
path, status=ok, git_commit, hardware, overall, utc`.
Gaps (-> Phase 1): no explicit MEASURED/SAMPLED/DERIVED/PENDING/UNAVAILABLE status;
revisions scattered (`packages`, `revision=null`, `data_path`); no single validated
enriched view (added in `result_schema.py`, backwards compatible).

## 3. Statistics / ranking (current)

`stats.py`: Wilson, continuity-corrected McNemar, Kendall tau-b, competition ranks
(average-tie), `pairwise_reversals`, `cis_overlap`/`ci_aware_ties`.
`report.py::ranking_table`: per-(factor,level) ranks vs control + tau + reversals +
McNemar vs control on paired ids. Documented in `STATISTICAL_METHODOLOGY.md`.
Gaps (-> Phases 2-4): no reusable variance/CV/bootstrap/effect-size module; no
Spearman, win-rates, rank distributions, P(#1), bootstrap rank stability; no
documented fragility components (added as `stability.py`, `ranking.py`).

## 4. Experiments / artifacts

`configs/experiments/stability.yaml`: 4 models x OFAT + `sampled` arm; T4 profile
skips 7B fp16/int8/vllm + paraphrase -> **34 cells**
(`test_stability_yaml_t4_skips_7b_fp16`). `paper/run_status.md` now 31/34 (hand);
`paper/_generated_tables.md` + `reports/stability_paper/` are generator outputs
(`make paper` / `make figures`). Rule: never invent rows; generated parts only
change via the pipeline.

## 5. Implemented vs planned / fragile spots

Verified: config-driven eval, HF/vLLM backends, OFAT+resume, registry+hashing,
Wilson/McNemar/Kendall, ranking+paper tables, reproduce CLI, 58 fixture tests.
Partial: thinking/paraphrase/robustness/hallucination/safety/cost/pareto (code
exists, T4 runs pending/skipped). Missing: status model, stability/ranking/
fragility libs, multi-factor designs, variance decomposition, EvalFrag, adaptive
eval, cost-vs-confidence, predictor (interface only), agent extension, runner.
Fragile: `report.py` (~850 lines) — extract helpers only with features, keep format
stable. `analysis.py` mixes many derived metrics — add new modules, don't grow it.
`sweep.py` stays OFAT-first; multi-factor is opt-in `expand_factorial` + budget.

## 6. Plan (this iteration, then next)

This iteration: audit + `RESEARCH_PLAN.md`, `result_schema.py`, `stability.py`,
`ranking.py`, `sweep.expand_factorial` + tests + docs; pytest green; small commits.
Next: fragility EFI (provisional + ablated), variance decomposition, EvalFrag seed
set, adaptive evaluator, cost-vs-confidence, predictor interface, agent schema,
experiment runner + report generation.
