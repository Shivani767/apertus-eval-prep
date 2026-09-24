# Industry Upgrade Plan: Apertus Eval Prep → LLM Evaluation & Release-Readiness Platform

Status: implemented in this change set (see `docs/ARCHITECTURE.md` for the as-built view).
Audit commit: `6b83cd0` (branch `feature/industry-grade-eval-platform`).
Audit method: direct inspection of every source module, config, test, workflow, and
artifact family in the working tree. The pre-change baseline was 263 passing
tests offline; the current suite is validated separately in the release notes.

Repository facts that constrain the plan (verified, not assumed):

* Python package `apertus_eval_prep` (src layout, setuptools), flat module
  layout plus one subpackage `backends/`. The pre-change baseline had 263 tests.
* Current core dependencies: `pyyaml`; `torch` and `transformers` are optional
  legacy-runtime dependencies, with `gpu`, `viz`, `snapshot`, and `dev` extras.
  No web framework, no pydantic, no numpy/scipy.
* Runner: `run_eval.run_eval(cfg, repo_root, checkpoint_path)` — the single
  execution path, producing one JSON blob per run into `results/`.
* Registry: append-only JSONL (`results/registry*.jsonl`) keyed by
  `config_hash` (16 hex chars, `registry.HASH_KEYS`).
* Analysis layer already exists and is good: `stats.py` (Wilson, McNemar,
  Kendall tau-b, paired bootstrap diff CI, sign-flip permutation test,
  Holm/BH, CI-width curve), `ranking.py`, `variance.py`, `stability.py`,
  `fragility.py`, `reliability.py`, `adaptive.py`, `metamorphic.py`.
* Reporting already exists: `report.py`, `benchmark_report.py`, `failures.py`,
  `pareto.py`, `cost.py`, `profile.py`, `dashboard.py`, `site.py` (static
  `site.json`) and a Vite/React frontend (`frontend/`) that consumes it.
* CI now includes the offline package installation, compile check, full test
  suite, and deterministic platform smoke workflow.

## 1. Current repository architecture

```
data/ (frozen slices, SOURCES.md, paraphrase_set, evalfrag seed)
  → prompts.load_items() → EvalItem
configs/*.yaml → config.load_config() → RunConfig (22 fields, comparable_settings())
  → sweep.load_study()/expand_ofat()/expand_factorial() → cells (RunConfig dicts)
run_eval.run_eval(cfg, repo_root, checkpoint_path) → run JSON blob
  → backends/{hf,vllm}.py, prompting.py, templates.py, scoring.py, checkpoint.py
  → manifest.build_manifest() (git SHA, dirty, platform, packages, hardware)
  → registry.config_hash() + results/registry*.jsonl
analysis: stats.py, ranking.py, variance.py, stability.py, fragility.py,
          reliability.py, adaptive.py, metamorphic.py, cost.py, pareto.py,
          failures.py, result_schema.py (MEASURED/SAMPLED/DERIVED/PENDING/UNAVAILABLE)
reporting: report.py, benchmark_report.py, dashboard.py, site.py
  → reports/** + frontend/public/data/** → Vite build → GitHub Pages
CLI: apertus_eval_prep.cli (eval, dump-prompts, compare, sweep, report,
     paper-tables, reproduce, benchmark-report, paper, ers, pareto, failures,
     dashboard, site, profile, catalog, experiment)
```

## 2. Current execution flow

1. `cli.main()` → `load_config(path, overrides)` → `RunConfig`.
2. `run_eval` loads items, resolves prompt spec/system prompt, picks backend
   (`hf` or `vllm`), renders prompts, loops items one-by-one with optional
   `.partial.jsonl` resume, scores each item, then aggregates
   (`tasks`/`latency`/`language`/`cost`).
3. CLI writes the blob to `--out`; `sweep` writes per-cell blobs into
   `results/runs/*.json` and appends `results/registry.jsonl`.
4. Analysis/report commands read the registry + blobs; `site` emits one
   compact `site.json` for the frontend.

## 3. Existing strengths to preserve

* Honest epistemics: `result_schema.py` status vocabulary, "never zero-fill
  missing measurements" discipline in `cost.py`/`pareto.py`.
* Statistical core (`stats.py`) with paired tests, multiplicity correction,
  and CI-aware tie handling — reused, not reimplemented.
* Provenance instinct (`manifest.py`) and config-hash comparability model.
* OFAT + factorial design expansion with hard cell budgets (`sweep.py`).
* Failure taxonomy, Pareto and cost layers already wired into the CLI.
* The pre-change audit identified 263 offline tests; the current suite expands this baseline with deterministic platform and artifact-boundary coverage. No test requires network, credentials, or a GPU.
* Curated artifacts committed intentionally (`results/`, `reports/`, `paper/`).

## 4. Pre-change technical debt and limitations

The list below records the repository state before this upgrade; it is retained as
historical context, not as a statement of the current implementation.

1. **No offline model adapter.** `VALID_BACKENDS = ("hf","vllm")`; every eval
   path needs `transformers`/`vllm` and (for vLLM/quantization) CUDA. Nothing
   in the platform can be executed end-to-end in CI.
2. **No run artifact contract.** A run is one JSON blob; there is no
   `runs/<run_id>/` directory, no immutable manifest, no separated raw
   outputs vs derived scores, no tool traces, no machine-readable gate result.
3. **No resolved-config artifact / dataset lock.** Dataset identity is a path
   string; there is no dataset hash, no prompt-template hash, no config hash
   inside the manifest (only in the registry row).
4. **No episode/multi-step evaluation.** Only single-turn generation: no tool
   schemas, tool traces, recovery measurement, retrieval, groundedness, or
   perturbation experiments.
5. **No safety layer.** No risk taxonomy, no sanitized adversarial fixtures,
   no attack-success-rate/risk-score reporting, no safety gate.
6. **No release-gate engine.** Passing/failing a release is a human reading of
   Markdown; no PASS/BLOCKED/INCONCLUSIVE contract, no precedence, no exit code.
7. **Robustness analysis is per-experiment, not per-run.** `variance.py` etc.
   operate on registries, so a single run cannot report "how unstable was I".
8. **No failure fingerprints.** `failures.py` counts a taxonomy for one blob;
   there is no per-run fingerprint, no dominant-mode profile, no prioritised
   investigation list, no cross-run regression of failure modes.
9. **Feeble PII/retention story.** Raw generations are always stored in full;
   no redaction, no retention switch, no secret scrub in reports.
10. **Run IDs are content hashes only** (`config_hash`), so two identical
    configs collide by design and a rerun silently overwrites the blob.
11. **No test CI (pre-change baseline).** A regression could reach `master` unnoticed; the current workflow adds offline CI.
12. **Docs are research-note shaped.** No ARCHITECTURE/METHODOLOGY/
    REPRODUCIBILITY/RELEASE_GATES methodology docs, no CONTRIBUTING.
13. **Repo hygiene.** Build artifacts tracked/open (`paper/main.aux|.bbl|.log|.out`,
    `paper/*.zip|tar.gz`, `out.pdf`, `paper/PROBE_DELETE_ME.txt`), no rules for
    future `runs/` output.
14. **No typed public API contract** for new surfaces; validation is ad-hoc
    (`load_config` does manual checks, good intent but undocumented).

## 5. Pre-change industry-readiness gaps (mapped to buyer questions)

| Question a model-release team asks | Pre-change gap |
|---|---|
| Did the model improve, or did the prompt/config change? | Partially answered by sweep+stats, but not by a comparable, artifact-backed run pair with a classification |
| Is a regression statistically meaningful? | Stats exist; no regression *classifier* with practical-effect thresholds, sample-size and safety overrides |
| How reliable across seeds/prompts/decoding/backends/quantization? | OFAT cells exist; no per-run robustness summary, no Robust Capability Score, no per-example condition-sensitivity labels |
| Which config is best under quality/safety/latency/cost/stability? | Pareto exists for 2 objectives only; no constraint-based selector, no rejection reasons |
| Can a RAG/agent system complete realistic multi-step tasks safely? | Nothing |
| What are the costly/severe failure modes? | Taxonomy counts only; no fingerprints, severities, or regressions of failure modes |
| Is this candidate ready for controlled release? | No gate engine, no statuses, no exit codes |
| Can I trust/audit a number? | No immutable run directory, no dataset/prompt hashes, no retention policy |

## 6. Target architecture

Extend the existing package (do not rewrite it) with four new subpackages and a
thin platform CLI that re-uses the legacy runner where it is still the right
tool:

```
src/apertus_eval_prep/
  utils/      hashing, serialization, pii, environment, logging
  core/       errors, schemas, config, provenance, artifacts, registry, runner
  adapters/   base, mock, local, openai_compatible
  tasks/      base, static_qa, rag_episode, agent_episode, perturbations
  evaluators/ quality, groundedness, safety, tool_use, cost_latency, judge_reliability
  metrics/    aggregate, confidence_intervals, paired_comparison,
              robustness, pareto, regression
  safety/     taxonomy, attack_templates, risk_scoring
  reporting/  markdown, html, release_gates, failure_fingerprint
  platform_cli.py   (nested `platform` subcommand group)
  <legacy modules unchanged: config, run_eval, stats, scoring, sweep, report, ...>
```

Guiding rules: legacy `RunConfig`/`run_eval`/registry/stats keep working exactly
as before; the platform layer is additive and imports downward (never the
reverse); no new runtime dependency is required for anything offline.

## 7. File-by-file implementation plan

New files (all created in this change set):

* `utils/hashing.py` — `canonical_json`, `stable_hash`, `hash_text`, `hash_file`,
  `hash_bytes`; deterministic across processes (sorted keys/sets, no `repr`).
* `utils/serialization.py` — `to_jsonable`, `write_json`, `read_json`,
  `append_jsonl`, `read_jsonl`, `write_yaml`, `read_yaml`, `atomic_write_text`;
  JSON-strict (non-finite floats → `null`).
* `utils/pii.py` — `RedactionPolicy`, `RedactionReport`, `redact_text`,
  `redact_structure`, `detect_sensitive`, `truncate_text`.
* `utils/environment.py` — `git_metadata` (graceful when git is absent/not a
  repo), `python_metadata`, `platform_metadata`, `hardware_metadata`,
  `package_versions`, `environment_snapshot`.
* `utils/logging_utils.py` — structured (JSON-lines or text) logger that
  redacts through the PII policy; never logs secrets.
* `core/errors.py` — typed exception hierarchy with stable `code` attributes.
* `core/schemas.py` — `Dimensions`, `AdapterSpec`, `PromptSpec`, `TaskSpec`,
  `DecodingSpec`, `RuntimeSpec`, `EvaluatorSpec`, `MetricsSpec`, `ReportingSpec`,
  `RunSpec`, `ExperimentSpec`; `from_dict`/`to_dict`, validation with field
  paths, optional future dimensions (`language`, `locale`, `domain`,
  `risk_category`, `deployment_environment`).
* `core/config.py` — YAML loading, `extends:` resolution with cycle detection,
  `load_run_spec`, `load_experiment_spec`, factor→path mapping, deterministic
  matrix expansion, `MAX_MATRIX_CELLS` budget.
* `core/provenance.py` — `build_run_manifest` (git, env, packages, model
  revision, dataset+prompt+config hashes, seed, backend/device/precision/
  quantization, entry-point command, `artifact_format_version`).
* `core/artifacts.py` — `RunStore` (immutable run directory, collision-resistant
  run IDs, no silent overwrite), `RetentionPolicy`, canonical artifact filenames,
  `iter_runs`, `load_run_manifest`.
* `core/registry.py` — `runs/index.jsonl` index with filters (`find_runs`).
* `core/runner.py` — orchestrates static-QA, RAG and agent episode runs;
  metrics + CIs + regression + gates + reports + index; labels every result
  `MOCK`/`MEASURED`; never reports synthetic fixtures as benchmarks.
* `adapters/base.py` — `ModelAdapter` protocol, `CompletionRequest`,
  `AdapterResponse`, `ToolCall`, `Usage`, `AdapterCapabilities`, `AdapterError`.
* `adapters/mock.py` — deterministic offline adapter: normal/structured/
  invalid/timeout/error/refusal/tool-call modes, seed-dependent variation,
  optional dataset oracle with a configurable skill profile (explicitly
  synthetic: used to exercise statistics, never presented as model evidence).
* `adapters/local.py` — wraps the existing `HFBackend`/`VLLMBackend` (lazy
  import, no hard dependency at import time).
* `adapters/openai_compatible.py` — stdlib HTTP adapter for self-hosted
  OpenAI-compatible endpoints; base URL/credentials from env or config only,
  network disabled unless explicitly enabled, auth headers never logged.
* `tasks/base.py` — episode/task schemas, `ToolSpec`, `ToolResult`,
  `ToolTraceRecord`, `parse_episode`, trace validation.
* `tasks/static_qa.py` — single-turn QA tasks over the existing frozen slices,
  re-using `scoring.is_correct`/`is_refusal`.
* `tasks/rag_episode.py` — deterministic keyword retrieval over episode
  context, citation extraction/validation, grounding inputs.
* `tasks/agent_episode.py` — episode loop: tool calls, schema validation,
  retries/recovery, step and unsafe-action accounting, traces.
* `tasks/perturbations.py` — safe deterministic perturbations: drop evidence,
  distractor, contradictory source, stale source, truncate context, retrieval
  failure, tool timeout/error, sanitized retrieval-injection detection probe.
* `evaluators/quality.py` — quality outcomes, refusal accounting, aggregation.
* `evaluators/groundedness.py` — auditable rule-based groundedness (claim
  support by token overlap + citation validation), optional judge adapter,
  explicit uncertainty/caveats.
* `evaluators/safety.py` — taxonomy-driven case scoring (refusal, safe
  alternative heuristic, attack success, benign false refusal).
* `evaluators/tool_use.py` — schema validity, sequence validity, unnecessary
  calls, efficiency, recovery, step counts, unsafe actions.
* `evaluators/cost_latency.py` — latency percentiles, token usage, cost model
  (`PriceBook`, estimates labelled; missing prices → unavailable, never 0),
  cost per successful task.
* `evaluators/judge_reliability.py` — agreement rate, Cohen's kappa, confusion
  matrix, judge-vs-human report.
* `metrics/aggregate.py` — `summarize` (n, mean, median, stdev, stderr, min,
  max, percentiles, n_missing) and failure/reason accounting.
* `metrics/confidence_intervals.py` — Wilson (re-used) + bootstrap mean CI +
  percentile bootstrap, explicit small-sample behaviour.
* `metrics/paired_comparison.py` — paired bootstrap diff CI (re-used), McNemar,
  effect size (risk difference, Cohen's h), shared-example bookkeeping.
* `metrics/robustness.py` — condition variance, Robust Capability Score
  (experimental, configurable λ), per-example sensitivity classification,
  most-unstable-factor ranking.
* `metrics/pareto.py` — n-objective Pareto with domination explanations,
  maximize/minimize per objective, exclusion of unmeasured points.
* `metrics/regression.py` — `RegressionThresholds` + `classify_regression`
  producing CONFIRMED/LIKELY/NO_MEANINGFUL_CHANGE/INCONCLUSIVE with reasons,
  practical-effect threshold, sample size and optional safety-critical override.
* `safety/taxonomy.py` — severities, 11-category risk taxonomy, weights,
  case validation, YAML load.
* `safety/attack_templates.py` — sanitized, non-operational templates for each
  category (canary markers, abstract scenarios); render → `SafetyTestCase`.
* `safety/risk_scoring.py` — ASR, per-category pass rates, safe refusal rate,
  benign false-refusal rate, high-severity failure count, transparent
  severity×category weighted risk score with visible components, baseline
  comparison.
* `reporting/release_gates.py` — gate spec (`min`/`max`/`allow` rules, sections,
  watchlist bands, blocking statuses, precedence) and `evaluate_gates` →
  PASS / PASS_WITH_WATCHLIST / BLOCKED_* / INCONCLUSIVE.
* `reporting/failure_fingerprint.py` — 17-category failure taxonomy, failure
  records (hashes + sanitized excerpts + repro command), clustering, per-run
  fingerprint, priority investigations.
* `reporting/markdown.py` — full run report (provenance → limitations →
  reproduction command), experiment report, comparison report.
* `reporting/html.py` — dependency-free static HTML report (inline CSS,
  summary cards, tables, `<details>` traces, mock/measured badges, escaping).
* `platform_cli.py` — `platform run|matrix|compare|episodes|safety|gates|report
  |index|smoke`, exit codes, `--dry-run`, `--json`.
* `configs/platform/{smoke,agent_smoke,safety_smoke}.yaml`,
  `configs/experiments/platform_variance.yaml`,
  `configs/release_gates/{default,strict}.yaml`,
  `configs/pricing/example.yaml` (illustrative, clearly labelled, no real prices).
* `data/platform/{episodes_smoke,episodes_perturbation}.jsonl`,
  `data/platform/safety_cases.yaml` — small, curated, sanitized fixtures.
* `tests/test_platform_*.py` + `tests/integration/test_platform_*.py` +
  `tests/fixtures/platform/*`.
* Docs: `INDUSTRY_UPGRADE_PLAN.md` (this file), `ARCHITECTURE.md`,
  `METHODOLOGY.md`, `REPRODUCIBILITY.md`, `EXPERIMENT_DESIGN.md`,
  `AGENT_RAG_EVALUATION.md`, `SAFETY_EVALUATION.md`, `RELEASE_GATES.md`,
  `FAILURE_ANALYSIS.md`, `EXTENDING_THE_PLATFORM.md`, `CONTRIBUTING.md`.
* `.github/workflows/ci.yml` — offline lint+tests+smoke artifacts (no secrets).

Modified files: `pyproject.toml` (version and optional dependencies), `README.md` (new positioning + platform quickstart, legacy content preserved), `cli.py` (register `platform` subcommands), `Makefile` (platform targets), and `.gitignore` (`runs/`, generated platform reports).

## 8. New dependencies and justification

| Dependency | Where | Why | Required offline? |
|---|---|---|---|
| `pyyaml` | core configuration/serialization | typed YAML and safe artifact I/O | yes |
| `pytest` | `dev` extra | deterministic test suite | no |
| `torch`, `transformers` | `legacy` extra | optional HF research backend | no |
| `vllm`, `bitsandbytes` | `gpu` extra | optional GPU/quantized backends | no |

Deliberately **not** added: pydantic (dataclass validation matches repo style and
keeps the dependency surface small), numpy/scipy/pandas (bootstrap and statistics
are pure-Python and already partly implemented in `stats.py`),
flask/fastapi/streamlit (static HTML keeps the existing static-site approach),
requests/httpx (stdlib `urllib` is enough for one optional adapter).

## 9. Compatibility and migration strategy

* Nothing is deleted: `config.py`, `run_eval.py`, `sweep.py`, `stats.py`,
  `report.py`, `registry.py`, `result_schema.py`, `cost.py`, `pareto.py`,
  `failures.py`, `site.py` and the whole legacy CLI keep their behaviour and
  signatures.
* `registry.config_hash` and `HASH_KEYS` are untouched, so committed
  `results/registry*.jsonl` rows and every published number stay valid.
* Legacy `results/` artifacts keep the current format; new platform runs go to
  `runs/<run_id>/` (`runs/index.jsonl`), git-ignored by default.
* `stable_hash` is a new function; legacy hashes are never recomputed.
* The platform CLI is additive: new nested `platform` subcommands; existing
  subcommands and exit codes are unchanged.
* `import apertus_eval_prep` stays dependency-light: `torch`/`transformers` are
  imported only inside optional legacy backend modules when those backends are used.

## 10. Testing strategy

* Unit tests per module with deterministic fixtures (no network, no API keys,
  no GPU, no dependence on wall-clock other than run-ID uniqueness).
* Integration tests: static-QA smoke run, 8-cell experiment matrix with parent
  experiment report, RAG/agent episode run with perturbations, safety suite,
  gate evaluation over a produced run, CLI end-to-end.
* Synthetic-but-honest fixtures: the mock adapter's oracle is explicitly
  labelled synthetic; tests assert `MOCK`/`synthetic` labels are present so
  fixture scores can never be mistaken for measurements.
* Statistical tests use hand-computed expectations (e.g. Wilson bounds) plus
  boundary tests for regression statuses and gate precedence.
* Validation performed at the end of this change set: `python -m pytest -q` (286 passing),
  `python -m py_compile` over `src`, deterministic platform smoke/safety/episode/matrix
  workflows, release-gate evaluation, and a credential-marker scan of produced
  artifacts. Ruff was not available in the validation environment and is not
  claimed as a passing check.

## 11. Security and privacy considerations

* No secrets in code, configs, fixtures, or reports. The OpenAI-compatible
  adapter reads credentials from env/argument and redacts `Authorization`,
  `api_key`, `token`, `secret`, `password`; headers are never logged/persisted.
* PII/secret redaction for logs and reports (`utils/pii.py`, on by default in
  platform configs) covering emails, phone-like numbers, card-like digit runs,
  IPv4 addresses, bearer/API-key shapes.
* Raw retention is configurable (`reporting.include_raw_outputs`,
  `max_excerpt_chars`); when disabled, raw text is replaced by hash + length so
  audits still work without storing content.
* Safety fixtures are sanitized and non-operational: abstract scenarios, canary
  markers, no harmful instructions or operational detail. Reports repeat that
  automated safety testing is not certification and that high-impact releases
  need human review.
* No paid provider URLs or prices hardcoded; cost data comes from config
  (`configs/pricing/example.yaml` is clearly illustrative).

## 12. Research contributions and novelty

1. **Evaluation Variance Lab** — first-class variation across seeds, prompt
   templates, system prompts, decoding, backend, precision/quantization, task
   and split, with per-child artifacts, parent experiment reports, and
   per-example condition-sensitivity labels.
2. **Robust Capability Score (RCS)** — `mean_quality − λ·configuration_variance`,
   reported with its components, λ configurable, explicitly an experimental
   project metric with documented limitations.
3. **Failure Fingerprints** — per-run category-level failure profile with
   severity, condition-sensitivity, stable-failure identification and ranked
   investigation priority, instead of a single aggregate score.
4. **Release Readiness Gates** — one decision contract over quality, CIs,
   regression class, safety, groundedness, tool-use reliability, latency, cost,
   failure rate and sample size, with explicit precedence and INCONCLUSIVE.
5. **RAG/Agent episode evaluation** — multi-step tasks with tool-schema
   validity, sequence validity, recovery after tool failure, groundedness and
   perturbation sensitivity (including sanitized retrieval-injection probes).

Thesis: *LLM benchmark scores are deployment-condition dependent; a reliable
evaluation platform must quantify capability together with variance across valid
deployment conditions, safety risk, groundedness, cost, latency and failure
modes.*

## 13. Phase completion checklist

* [x] Phase 0 — reproducibility foundation (resolved config, manifest, hashing,
      artifact store, mock adapter, PII-aware logging, smoke config + command)
* [x] Phase 1 — variance lab (matrix expansion, summaries, CIs, paired
      comparison, regression classifier, RCS, failure sensitivity, reporting)
* [x] Phase 2 — RAG/agent episodes (schemas, traces, metrics, perturbations,
      groundedness, synthetic English fixtures)
* [x] Phase 3 — safety and red teaming (taxonomy, sanitized templates, metrics,
      transparent risk score, safety gates, reporting)
* [x] Phase 4 — deployment efficiency and model selection (cost model, Pareto,
      constraint selector, release-gate engine)
* [x] Phase 5 — failure fingerprints (records, clustering, fingerprints)
* [x] Phase 6 — reporting, dashboard, docs, CI
* [x] Final validation — full test suite, lint, offline smoke, matrix,
      baseline/candidate comparison, episode run, safety run, gates, report
      generation, PII/secret scan, `.gitignore` hygiene
