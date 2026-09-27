# Final Audit

**Scope:** the whole repository at commit `221d1d2` (master), audited for Phase 9.
**Method:** direct inspection of source, docs, configs, tests, notebooks, workflows, and
committed artifacts, plus execution of the full offline validation battery. No model was
downloaded, no GPU was used, and no external API was called.

**Nature of this document:** a software and framework release. It is not a certified
production system, and it makes no model-safety or production-readiness claim.

---

## 1. Final architecture summary

The repository contains two coexisting layers, entered through one CLI.

**Typed platform (Phases 1–8).** Configuration-driven, artifact-first. A run spec in YAML
declares adapter, task, prompt, decoding, metrics, and reporting. Execution produces an
immutable run directory:

```text
<run_id>/
  manifest.json            identity, evidence mode, model, revision, hashes, runtime
  config.resolved.yaml     the fully resolved spec that produced this run
  dataset.lock.json        dataset + task fingerprints
  metrics.json             scored/failed/missing counts, means, intervals
  confidence_intervals.json
  gate_report.json         threshold evaluation + non-approval disclaimer
  failure_fingerprint.json derived, prompt-identity-independent grouping
  failures.jsonl           per-failure records
  scored_examples.jsonl    per-example outcomes (recomputable)
  raw_outputs.jsonl        what the model actually said (optional; --no-raw disables)
  report.md / report.html  evidence-labelled rendering
```

Identity is enforced, not assumed: `platform-compare`, `platform-ingest-runs`, and
`platform-study-analyze` all refuse to combine runs whose dataset, task, prompt, or metric
definition differs.

**Legacy research harness.** The original frozen-prompt OFAT harness (`eval`, `sweep`,
`report`, and related commands). Retained, tested, and still useful for reproducing the
early research narrative. Its artifacts predate the evidence-mode system.

**Module layout** (`src/apertus_eval_prep/`): `core/` (config, artifacts, evidence, errors,
runner), `adapters/`, `evaluators/`, `analysis/`, `experiments/`, `release/`, `review/`,
`study/`, `reporting/`, `utils/`, plus the legacy top-level modules.

**Dependency posture:** one runtime dependency (`pyyaml`). GPU runtimes are optional extras
imported lazily inside adapters, so the offline path and CI install and import nothing heavy.

## 2. Main platform capabilities

| Area | Capability | Entry point |
|---|---|---|
| Provenance | Immutable artifacts, resolved config, content hashes, git commit capture | `platform-run` |
| Evidence | Machine-checked evidence modes with consistency validation | `core/evidence.py` |
| Variance | Deterministic factor matrices, bootstrap/Wilson CIs, paired deltas, Kendall tau | `platform-matrix`, `platform-compare` |
| Robustness | Evaluation Reliability Score; experimental Robust Capability Score | `analysis/` |
| RAG/agent | Episode evaluation, tool traces, groundedness, turn budgets | `platform-episode` |
| Safety | Sanitized suite, category taxonomy, severity weighting, attack success | `platform-safety` |
| Deployment | Latency/cost points, Pareto frontier, constraint selection | `platform-ingest-runs`, `platform-select` |
| Gates | Threshold policies with disclaimers | `platform-gate` |

## 3. Public CLI command inventory

30 commands, all responding to `--help`. Full verified reference:
[`CLI_REFERENCE.md`](CLI_REFERENCE.md).

**Typed platform (13):** `platform-run`, `platform-matrix`, `platform-compare`,
`platform-episode`, `platform-safety`, `platform-report`, `platform-fingerprint`,
`platform-gate`, `platform-export-review`, `platform-ingest-review`, `platform-study-analyze`,
`platform-ingest-runs`, `platform-select`.

**Legacy harness (17):** `eval`, `dump-prompts`, `compare`, `sweep`, `report`,
`paper-tables`, `paper`, `ci-width`, `benchmark-report`, `reproduce`, `ers`, `pareto`,
`failures`, `dashboard`, `site`, `profile`, `catalog`, `experiment`.

## 4. Evidence-mode model

Defined in `src/apertus_eval_prep/core/evidence.py`. Eight modes: `MOCK`, `SYNTHETIC`,
`LOCAL_REAL_MODEL`, `EXTERNAL_PROVIDER`, `HARDWARE_MEASURED`, `HUMAN_VALIDATED`, `MIXED`,
`UNKNOWN`. Grouped as `SYNTHETIC_EVIDENCE_MODES` and `REAL_EVIDENCE_MODES`.

Two properties were verified by execution and by test:

- **Consistency is enforced, not documented.** `normalize_evidence` raises `ValueError` for
  contradictory declarations, e.g. `MOCK` with `real_model_execution=true`, or
  `LOCAL_REAL_MODEL` without it.
- **Inference is deliberately conservative.** `infer_evidence_mode` never promotes an
  unrecognized legacy class to a real mode; it returns `UNKNOWN`, because under-claiming is
  recoverable and over-claiming is not.

Missing evidence is preserved as unavailable. `platform-select` emitted
`insufficient_evidence: true` rather than a recommendation when the evidence did not support
one.

## 5. Offline/mock versus optional real-model capabilities

**Always available** (base install, CPU, no network): the mock adapter, all statistics,
matrices, comparisons, episodes, safety suite, gates, fingerprints, reports, deployment
selection, study aggregation, and review tooling. This is what CI exercises.

**Optional** (`[real-model]`: torch, transformers, accelerate): local open-weight model
execution, recorded as `LOCAL_REAL_MODEL` with full hardware and revision provenance. Gated
repositories additionally require a Hugging Face token, handled by
`apertus_eval_prep.hub_auth` — which validates each candidate token against `whoami`, prefers
the Colab secret over a cached token, and proves the download by fetching `config.json`
before GPU time is spent.

This separation is the direct cause of a documented fix in this release: three earlier
Gemma/Llama runs scored 0 of 257 because the notebook preflight called `model_info`, which
succeeds anonymously for a gated repository, and accepted any ambient token without
validating it. The preflight reported success while every download returned 401.

## 6. Research/study workflow

1. **Protocol** — `docs/PHASE8_STUDY_PROTOCOL.md` declares the research question,
   hypotheses, and decision rules before data collection.
2. **Preregistration** — `docs/PHASE8_PREREGISTRATION_TEMPLATE.md` records the plan, sample
   counts, and stopping rule.
3. **Configuration** — a study YAML under `configs/studies/` declares the matrix (models,
   prompt templates, seeds, dtype, quantization, decoding), the suites, the gate policy, and
   the evidence mode. Placeholders such as `REPLACE_WITH_INVESTIGATOR` are left visible.
4. **Execution** — `platform-matrix` expands the matrix; each cell writes its own artifacts
   and records the parent experiment id.
5. **Deviations** — `docs/PHASE8_DEVIATION_LOG_TEMPLATE.md` records anything that changed.
6. **Aggregation** — `platform-study-analyze` refuses incompatible runs (different
   `study_id`, missing required artifacts) rather than silently aggregating them, and
   reports the evidence modes present plus `real_model_evidence_available`.
7. **Review** — optional human review via export/ingest (below).

**Deviation handling is real, not aspirational:** the three failed gated-model runs were
recorded under `results/colab_failed_runs/` with their recorded causes, kept outside every
comparison, rather than being dropped or presented as results.

## 7. Human-review workflow

`platform-export-review` samples from a run (random, stratified, or priority), redacts, and
emits a sanitized JSONL package with `human_reviewed: false`. Annotators complete it.

## 8. Reproducibility guarantees

| Guarantee | Mechanism |
|---|---|
| A run is reconstructable | `config.resolved.yaml` is written with the run |
| Data identity is checkable | `dataset.lock.json` content hashes; `task_hash` |
| Code identity is recorded | git commit and dirty flag in the manifest |
| Model identity is recorded | model id **and** revision; unpinned `main` is flagged |
| Environment is recorded | hardware profile, precision, quantization, backend |
| Metrics are recomputable | `scored_examples.jsonl` holds per-example outcomes |
| Comparisons are honest | identity checks refuse mismatched runs |
| Reports are rebuildable | `platform-report` regenerates from artifacts without a model |
| CI is deterministic | mock fixtures, fixed seeds, no network, CPU-only |

**Not guaranteed:** exact reproduction of a run recorded against an unpinned `main`, and
exact reproduction on different hardware (floating-point and kernel differences). Both are
recorded as warnings in the affected summaries.

## 9. Security/privacy posture

Full detail in [`SECURITY_AND_PRIVACY.md`](SECURITY_AND_PRIVACY.md) and
[`../SECURITY.md`](../SECURITY.md).

- The realistic exposure is **disclosure through committed artifacts**, not remote
  exploitation. The library is not a network service and exposes no port.
- Automated controls: credential and PII redaction, structural scrubbing of sensitive keys,
  HTML escaping, sanitized review export, a CI secret guard, bounded and redacted error
  details, and token non-disclosure in `hub_auth`.
- **Pattern-based redaction is a reduction, not a guarantee.** It cannot find secrets in
  unfamiliar formats or sensitive content in free text.
- **Raw output retention is the main risk.** `raw_outputs.jsonl` preserves what the model
  said, which is what makes runs auditable and also where sensitive content appears.
  `--no-raw` disables it; `platform-export-review` produces a shareable subset.
- No telemetry, no analytics, no network calls of its own. Outbound traffic comes only from
  real-model adapters and the gated-model preflight.

## 10. Dependency and optional-extras summary

**Direct runtime dependency: one.** `pyyaml>=6.0`. Everything else is optional.

| Extra | Contents | Why it exists |
|---|---|---|
| `dev` | `pytest>=8.0` | the test suite and CI |
| `real-model` | torch, transformers, accelerate | local open-weight execution (`LOCAL_REAL_MODEL`) |
| `legacy` | torch, transformers | the older HF research harness |
| `gpu` | vllm, bitsandbytes | vLLM backend and quantized loading |
| `viz` | matplotlib | figures for research reports |
| `snapshot` | datasets, huggingface_hub | dataset snapshots and Hub inspection |

**Audit result:** no unused direct dependency was found, so none was removed. Optional
runtime imports are confined to adapter modules; verified by importing the CLI and asserting
that none of `torch`, `transformers`, `vllm`, `accelerate` enters `sys.modules`. Versions
use floors (`>=`) rather than pins — a deliberate trade-off documented in
[`SECURITY_AND_PRIVACY.md`](SECURITY_AND_PRIVACY.md#supply-chain).

## 11. CI validation strategy

`.github/workflows/ci.yml` — "Offline evaluation CI", triggered on push, pull request, and
manual dispatch, with `permissions: contents: read`.

```text
checkout -> setup-python 3.11 (pip cache)
         -> pip install -e '.[dev]'
         -> python -m compileall -q src
         -> python -m pytest -q
         -> platform-run --config configs/platform_smoke.yaml --out runs/ci-smoke
         -> upload report.*, failure_fingerprint.json  (if-no-files-found: error)
```

Properties: no secrets, no network dependency, no GPU, no model download, CPU-only, and a
single runtime dependency. The upload step uses `if-no-files-found: error`, so a run that
silently produced no artifacts fails the job rather than passing quietly.

A second workflow, `deploy.yml`, publishes the static research dashboard to GitHub Pages.
It is intentionally kept tracked in `.gitignore` via force-include rules.

`platform-ingest-review` validates and computes agreement.

Verified behaviour:

- An annotation not marked completed raises `ReviewValidationError: annotation is not
  completed` — an unfinished review can never be reported as agreement.
- Annotations that stay synthetic keep `human_reviewed=false`.
- Agreement is reported as **annotator consistency**, not correctness or safety.

**No completed human-review artifacts are included in this repository**, so no
human-validation claim is made anywhere. The templates and protocol are a tooling offering.

| Diagnostics | Failure fingerprints and investigation priorities | `platform-fingerprint` |
| Reporting | Evidence-aware Markdown/HTML, escaped dynamic content | `platform-report` |
| Study | Study configs, preregistration, aggregation with compatibility checks | `platform-study-analyze` |
| Human review | Sanitized export, strict validation, agreement | `platform-export-review`, `platform-ingest-review` |

## 12. Known limitations

1. **Condition-specific evidence.** Every real-model number is a property of model + prompt +
   decode + backend + hardware + dataset. None of it transfers automatically.
2. **Small samples.** The core suite is 38 items and the safety suite 11, so confidence
   intervals are wide. The platform reports them rather than hiding them.
3. **Protocol artefact in core scores.** The harness sends raw text without applying a chat
   template, so part of the core score measures terse format compliance. Four of seven
   curated models score exactly `0.0000` for this reason. Fixing it is a protocol change
   altering `metric_definition_version`, requiring a re-run of every model.
4. **Mostly unpinned revisions.** Six of seven curated models record `main`, so they are not
   exactly reproducible from the manifest alone. Recent notebooks pin a commit SHA.
5. **No human-review artifacts.** Tooling is shipped and tested; annotations are not, so no
   human-validation claim is made.
6. **Safety is a suite, not a guarantee.** An automated red-team evaluation over a declared
   taxonomy; it does not generalize to untested categories.
7. **Latency and cost are experimental.** Client-side wall-clock on ephemeral Colab/local
   hardware; no provider pricing is embedded, so cost is unavailable unless supplied.
8. **Groundedness is heuristic.** Lexical support against retrieved context, not factuality.
9. **Legacy artifacts lack evidence modes.** `results/*.json`, `registry*.jsonl` predate the
   typed platform; they are research artifacts, not platform evidence.
10. **Study layer does not enforce preregistration.** It aggregates compatible runs; it does
    not verify that the protocol was followed, nor correct for optional stopping.

## 13. Explicit non-goals

This project is not, and does not aim to be:

- a benchmark, a leaderboard, or a model ranking;
- a model-safety certification or red-team certification program;
- a production deployment, serving runtime, or inference engine;
- a substitute for organizational governance, privacy review, security review, or human
  approval;
- a claim of universal model performance;
- a host for provider integrations, hosted infrastructure, or distributed execution;
- a replacement for domain-specific evaluation or human judgement.

## 14. Compatibility notes

| Item | Status |
|---|---|
| Python | `>=3.10` required. CI validates 3.11. Developed and validated on 3.13/3.14. |
| Platform | Linux and macOS. No OS-specific behaviour in the offline path. |

## 15. Repository-hygiene findings

Findings from the audit, and their disposition in this release.

| # | Finding | Severity | Disposition |
|---|---|---|---|
| 1 | `patch_gated_auth_cell.py` duplicated at the repository root and in `scripts/` | Medium | Root copy removed; `scripts/` is canonical |
| 2 | `test_notebook_hub_auth.py` duplicated at the root and in `tests/`, and the root copy was **stale** (it asserted a notebook property the generator deliberately relaxes) | High | Root copy removed; `tests/` is canonical |
| 3 | `update_factorial.py` at the root: an unreferenced one-off manuscript helper containing a hardcoded absolute user path | Medium | Removed; a personal editing script, not project code |
| 4 | `.gitignore` had duplicate `.ipynb_checkpoints/` and duplicate `.env` patterns, with `runs/` separated from its explanatory comment | Low | Deduplicated and commented |
| 5 | `.gitignore` did not cover SSH private keys, coverage artifacts, `.tox`/`.nox`, or the Vite cache | Low | Added |
| 6 | README badges claimed **124** passing tests (actual: 383) and an **MIT** license (actual: Apache-2.0) | Medium | Corrected; both were factually wrong |
| 7 | `docs/METHODOLOGY.md` described an evidence vocabulary (`DEMONSTRATION`, `MEASURED`, `PROJECT_METRIC`) that **no longer exists in the code** | High | Replaced with the eight actual modes from `core/evidence.py` |
| 8 | `CITATION.cff` shipped a placeholder DOI, `10.5281/zenodo.TODO` | High | `doi` field removed entirely; a comment records how to add a real one |
| 9 | No `CHANGELOG.md`, `SECURITY.md`, or `CODE_OF_CONDUCT.md` | Medium | Created |
| 10 | No CLI reference; commands were discoverable only via `--help` | Medium | `docs/CLI_REFERENCE.md` created from verified `--help` output |
| 11 | README had no claim-boundary section and cited model numbers without an evidence label | High | "Evidence and Claim Boundaries" added to README and METHODOLOGY |
| 12 | `pyproject.toml` version was `0.5.0` while the project was at Phase 9 | Low | Bumped to `1.0.0` |
| 13 | The local working branch `integrate-phase8-colab` had **diverged** from master (34 commits behind, not an ancestor) with 40 uncommitted changes | High | Phase 9 executed in a clean worktree from `origin/master`; the stale branch was left untouched and is not part of this release |

Secret scan result: **clean** — no Hugging Face tokens, API keys, AWS keys, or private keys
in tracked files. Locations and categories only were inspected; no values were printed.

## 16. Release-readiness checklist

See [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) for the full list with verification
commands. Summary of this release:

- [x] Full test suite passes (383 tests), offline and CPU-only.
- [x] `compileall` clean; notebooks valid JSON with parseable code cells.
- [x] All 30 commands respond to `--help`; every documented command and option verified.
- [x] Offline smoke, report, fingerprint, gate, matrix, episode, safety, ingest, select,
      review, and study paths executed successfully.
- [x] Secret scan clean; `test_no_secrets_committed.py` passes.
- [x] Repository hygiene findings addressed.
- [x] Claim boundaries documented centrally in README and METHODOLOGY.
- [x] Changelog, security, code of conduct, CLI reference, FAQ, and checklist created.
- [x] Version bumped to `1.0.0`; CITATION.cff carries no placeholder DOI.
- [x] License decision: **Apache-2.0 exists** and is documented in the README. No license
      guidance file is needed; the owner already made the choice.
- [ ] Version tag `v1.0.0` — maintainer action.
- [ ] GitHub release notes published — maintainer action.
- [x] Known limitations reviewed and recorded above.

## 17. Statement of release nature

**This is a software and framework release, not a certified production system.**

The repository delivers an evaluation and release-readiness *framework*: reproducible
artifacts, evidence labelling, statistical and operational analysis, and reporting. It does
not deliver, and must not be represented as delivering:

- certification that any model is safe;
- approval of any model, prompt, or configuration for production use;
- production or serving benchmarks;
- human validation of any result (no completed review artifacts are included);
- evidence of universal model performance.

Real-model evidence in `results/colab_real_model/` is experimental and condition-specific.
Read each model's `summary.md`, including its warnings, before quoting any number.

| Offline path | Pure Python + `pyyaml`. No compiled extension required. |
| Optional GPU path | Validated on Linux with CUDA 12.8 and a T4 (14.6 GiB). |
| Artifact schema | `schema_version: "1.0"`. Consumers should check it rather than assume. |
| Evidence modes | Additive; new modes may be appended, so treat unknown modes as `UNKNOWN`. |
| Config schema | Typed with dotted overrides (`--set decoding.seed=2`). |
| Legacy harness | Retained and tested; not deprecated, but its artifacts carry no evidence mode. |
| Frontend | Static site, `tsc -b` and vitest; independent of the Python package. |

| Real models | Optional adapters, gated-repo auth, Colab notebooks, export/ingest | `adapters/`, `hub_auth.py`, `notebooks/` |
