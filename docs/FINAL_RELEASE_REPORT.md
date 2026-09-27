# Final Release Report

**Project:** Apertus Eval Prep
**Version:** 1.0.0
**Release date:** 2026-09-27
**Audit basis:** `docs/FINAL_AUDIT.md`, validated by execution at commit `221d1d2` plus the
Phase 9 changes described there.

---

## 1. Executive project summary

Apertus Eval Prep is a reproducible LLM evaluation and release-readiness platform for
measuring capability, reliability, safety, RAG/agent behavior, latency, cost, deployment
trade-offs, and failure patterns under declared experimental conditions.

The premise is that a single benchmark score hides more than it reveals. It conceals prompt
sensitivity, seed and decode variance, backend and quantization effects, RAG and agent
failures, groundedness regressions, safety trade-offs, latency/cost trade-offs, and
condition-sensitive failure patterns. The platform makes the evaluation configuration part
of the claim rather than a footnote to it.

What it delivers is instrumentation and evidence discipline: immutable artifacts, machine-
checked evidence labels, identity checks that refuse invalid comparisons, statistics with
visible uncertainty, and reports that preserve missing evidence as unavailable rather than
zero.

**What it is not:** a benchmark, a leaderboard, a safety certification, a production system,
or evidence of universal model performance.

## 2. Final architecture

Two layers behind one CLI.

- **Typed platform** — YAML run spec in, immutable artifact directory out, with identity,
  evidence mode, content hashes, git commit, and hardware provenance recorded. Enforced by
  comparison, ingestion, and study commands that refuse mismatched runs.
- **Legacy research harness** — the original frozen-prompt OFAT harness, retained and
  tested for the early research narrative; its artifacts predate evidence modes.

One runtime dependency (`pyyaml`). GPU runtimes are optional extras imported lazily inside
adapters, so the offline path and CI install and import nothing heavy.

```text
config (YAML) -> CLI -> {runner | matrix | episodes | safety}
   -> immutable run dir (manifest, metrics, CIs, gate, fingerprints, reports)
   -> {reports | gates | deployment selection | study | human review}
```

## 3. Phase 1–9 completion summary

| Phase | Delivered |
|---|---|
| 1 | Typed config, immutable artifacts, provenance, evidence modes, identity checks |
| 2 | Variance lab, bootstrap/Wilson CIs, paired decisions, Kendall tau, ERS, experimental RCS |
| 3 | RAG and agent episode evaluation with tool traces and groundedness |
| 4 | Safety suite, category taxonomy, severity weighting, red-team evaluation |
| 5 | Latency/cost points, Pareto frontier, constraint selection, release gates |
| 6 | Evidence-aware Markdown/HTML reporting, failure fingerprints |
| 7 | Optional real-model adapters, gated-repo auth, Colab workflow, curated real-run evidence |
| 8 | Study configuration, preregistration and deviation templates, aggregation, human review |
| 9 | Final audit, claim boundaries, release packaging, repository hygiene, this report |

## 4. Capability matrix

| Capability | Status | Evidence tier |
|---|---|---|
| Provenance and immutable artifacts | Complete | all |
| Variance and statistical analysis | Complete | all |
| RAG and agent evaluation | Complete | all |
| Safety evaluation | Complete | all |
| Deployment metrics and selection | Complete | all |
| Release gates | Complete — policy aid, not approval | all |
| Failure fingerprints | Complete | all |
| Evidence-aware reports | Complete | inherits run tier |
| Offline CI | Complete — offline, CPU-only, deterministic | `MOCK` |
| Optional real-model / Colab workflow | Complete — exercised on 7 models | `LOCAL_REAL_MODEL` |
| Study workflow | Complete — exercised on `MOCK` study | `MOCK` |
| Human review | Tooling complete and tested; **no completed annotations included** | n/a |

## 5. Evidence-mode matrix

| Mode | Present in this release | Claim it supports |
|---|---|---|
| `MOCK` | Yes — CI, offline smoke, most examples | the framework computes what it claims |
| `SYNTHETIC` | Yes | framework behaviour, not model behaviour |
| `LOCAL_REAL_MODEL` | Yes — 7 models under `results/colab_real_model/` | model behavior under the recorded configuration only |
| `EXTERNAL_PROVIDER` | Supported; no provider adapter shipped | provider responses, when configured |
| `HARDWARE_MEASURED` | Yes — latency tagged separately | latency on declared hardware, not serving latency |
| `HUMAN_VALIDATED` | **No completed artifacts** | none — no human-validation claim is made |
| `MIXED` | Used when aggregation spans modes | reported explicitly, never silently merged |

## 6. Public CLI inventory

30 commands: 13 typed-platform (`platform-*`) and 17 legacy harness. All verified against
`--help`. Full signatures in [`CLI_REFERENCE.md`](CLI_REFERENCE.md).

## 7. Documentation inventory

| Area | Documents |
|---|---|
| Release | `CHANGELOG.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `CITATION.cff`, `LICENSE` |
| Audit and release | `docs/FINAL_AUDIT.md`, `docs/FINAL_RELEASE_REPORT.md`, `docs/RELEASE_CHECKLIST.md` |
| Usage | `README.md`, `docs/FAQ.md`, `docs/CLI_REFERENCE.md`, `docs/VALIDATION.md` |
| Method and claims | `docs/METHODOLOGY.md`, `docs/STATISTICAL_METHODOLOGY.md`, `docs/REPRODUCIBILITY.md` |
| Architecture and extension | `docs/ARCHITECTURE.md`, `docs/EXTENDING_THE_PLATFORM.md` |
| Subsystems | `AGENT_RAG_EVALUATION.md`, `SAFETY_EVALUATION.md`, `RELEASE_GATES.md`, `FAILURE_ANALYSIS.md`, `EVALUATION_COST.md`, `METAMORPHIC_EVAL.md` |
| Real models | `REAL_EVALUATION_PROTOCOL.md`, `COLAB_EXPERIMENT_GUIDE.md` |
| Study and review | `PHASE8_STUDY_PROTOCOL.md`, `PHASE8_PREREGISTRATION_TEMPLATE.md`, `PHASE8_DEVIATION_LOG_TEMPLATE.md`, `HUMAN_REVIEW_PROTOCOL.md`, `ANNOTATION_GUIDELINES.md` |
| Security and privacy | `SECURITY.md`, `docs/SECURITY_AND_PRIVACY.md` |

## 8. Validation and test results

All executed offline, CPU-only, with no model download, no GPU, and no external API.

| Check | Result |
|---|---|
| `python -m pytest -q` | **383 passed**, 0 failed |
| `python -m compileall -q src` | clean |
| Offline smoke (`platform-run`) | artifacts written, `MOCK` labelled |
| `platform-matrix` | matrix expanded, per-cell artifacts |
| `platform-episode` (RAG and agent) | `evidence_class: MOCK` |
| `platform-safety` | `evidence_class: MOCK` |
| `platform-report` | `report.md` and `report.html` written |
| `platform-fingerprint` | fingerprint rebuilt |
| `platform-gate` | evaluated; payload carries the non-approval disclaimer |
| `platform-ingest-runs` → `platform-select` | points written; frontier returned; `insufficient_evidence: true` when evidence is thin |
| `platform-export-review` | sanitized package; `human_reviewed: false` |
| `platform-ingest-review` (incomplete) | correctly rejected: `annotation is not completed` |
| `platform-study-analyze` | aggregated; `evidence_modes: ["MOCK"]`, `real_model_evidence_available: false` |
| Study with a foreign `study_id` | correctly rejected: `study run artifacts are incompatible` |
| Matrix config without `experiment:` | correctly rejected, naming the missing field |
| `--help` for all 30 commands | all respond |
| Notebook JSON + code-cell syntax | 13 notebooks parsed, 0 syntax errors |
| `git diff --check` | clean |
| Secret scan | **no matches** (tokens, API keys, AWS keys, private keys) |
| Mock path import isolation | none of `torch`, `transformers`, `vllm`, `accelerate` imported |
| Report HTML checks | evidence label present, gate disclaimer present, dynamic content escaped |

Two validation attempts failed for reasons that turned out to be **correct behaviour**, and
are worth recording because they demonstrate the guarantees working:

- `platform-matrix --config configs/platform_smoke.yaml` → `experiment.base: is required`.
- `platform-study-analyze` over `tests/fixtures/phase7_runs` → `study run artifacts are
  incompatible` (those fixtures belong to a different study id).

Both refused to produce a result rather than aggregating something misleading.


## 9. Security and privacy posture

The realistic exposure is **disclosure through committed artifacts**, not remote
exploitation: the library is not a network service and exposes no port.

Automated controls: credential and PII redaction, structural scrubbing of sensitive keys,
HTML escaping, sanitized review export, a CI secret guard (`test_no_secrets_committed.py`),
redacted and bounded error details, and token non-disclosure in `hub_auth`.

Two honest limits are stated in the project's own documentation: pattern-based redaction is a
**reduction, not a guarantee** of anonymization, and `raw_outputs.jsonl` retention — which is
what makes runs auditable — is also the most likely place for sensitive content to appear.
`--no-raw` and `platform-export-review` exist for that reason.

No telemetry, no analytics, and no network calls of the framework's own.

## 10. Reproducibility properties

| Property | Mechanism |
|---|---|
| Run reconstructability | `config.resolved.yaml` written with every run |
| Data identity | `dataset.lock.json` hashes, `task_hash` |
| Code identity | git commit and dirty flag in the manifest |
| Model identity | model id and revision; unpinned `main` flagged as a warning |
| Environment | hardware profile, precision, quantization, backend |
| Metric recomputability | `scored_examples.jsonl` per-example outcomes |
| Comparison honesty | identity checks refuse mismatched runs |
| Report rebuildability | `platform-report` regenerates without a model |
| CI determinism | mock fixtures, fixed seeds, no network, CPU-only |

Not guaranteed: exact reproduction of a run recorded against `main`, or across different
hardware.

## 11. Research-study workflow

Protocol → preregistration → study configuration → matrix execution → deviation log →
aggregation → optional human review. Aggregation refuses incompatible runs rather than
merging them, and reports the evidence modes present.

## 12. Human-review workflow

Export a sanitized package → annotators complete it → ingest validates and computes
agreement. Incomplete annotations are rejected outright, synthetic annotations stay
`human_reviewed: false`, and agreement is described as annotator consistency rather than
correctness or safety. **No completed annotations are included in this release**, so no
human-validation claim is made.

## 13. Known limitations

See `docs/FINAL_AUDIT.md` §12 for the full list. The most consequential: evidence is
condition-specific; samples are small (38 core, 11 safety items); core scores partly measure
terse format compliance because no chat template is applied, which is why four of seven
curated models score exactly `0.0000`; most curated runs record an unpinned `main`; no
human-review artifacts are included; safety results cover a declared taxonomy only; latency
and cost are client-side experimental measurements; groundedness is a lexical heuristic; and
legacy artifacts under `results/` carry no evidence mode.

## 14. Explicit non-goals

Not a benchmark or leaderboard; not a safety certification; not a production deployment or
serving runtime; not a substitute for governance, privacy, security, or human approval; not a
claim of universal model performance; not a host for provider integrations or distributed
execution.

## 15. Suitable use cases

- Reproducing a declared evaluation on your own data.
- Comparing prompt, backend, seed, or quantization changes under matched identity.
- Regression-testing a prompt or serving backend against committed failure fingerprints.
- Measuring RAG and agent reliability, and safety risk against a declared taxonomy.
- Selecting a deployment configuration from measured latency/cost/quality trade-offs.
- Teaching evaluation methodology and evidence discipline.

## 16. Unsuitable use cases

- Certifying that a model is safe.
- Approving a release or a configuration for production.
- Producing production or serving benchmarks from this repository's latency data.
- Claiming human validation without completed review artifacts.
- Generalizing any result beyond its recorded configuration.
- Ranking models for publication using the core means as-is, given the format-compliance
  artefact.


## 17. Exact commands

All verified at this release.

**Offline validation** (no GPU, no network, no API keys):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m compileall -q src
python -m pytest -q
python -m apertus_eval_prep platform-run --config configs/platform_smoke.yaml --out runs/ci-smoke
```

**Optional real-model experiment:**

```bash
pip install -e ".[real-model]"
python3 scripts/build_real_model_notebooks.py     # generate one notebook per model
# open notebooks/real_model_<slug>.ipynb in Colab, T4 GPU, run all cells, export the zip
python -m apertus_eval_prep platform-ingest-runs --runs <run_dir> --out points.json
```

**RAG / agent evaluation:**

```bash
python -m apertus_eval_prep platform-episode --config configs/platform_phase3_rag.yaml   --out runs/rag
python -m apertus_eval_prep platform-episode --config configs/platform_phase3_agent.yaml --out runs/agent
```

**Safety evaluation** (red-team evaluation, not a certification):

```bash
python -m apertus_eval_prep platform-safety --config configs/platform_phase4_safety.yaml --out runs/safety
python -m apertus_eval_prep platform-gate    --run runs/safety/<run_id>
```

**Deployment selection:**

```bash
python -m apertus_eval_prep platform-ingest-runs --runs runs/smoke/<run_id> --out points.json
python -m apertus_eval_prep platform-select      --points points.json --out selection.json
```

**Human review export and ingestion:**

```bash
python -m apertus_eval_prep platform-export-review --run runs/smoke/<run_id> --out review.jsonl
# annotators complete review.jsonl
python -m apertus_eval_prep platform-ingest-review --input review.jsonl --out review_summary.json
```

**Study analysis:**

```bash
python -m apertus_eval_prep platform-matrix --config configs/studies/phase8_mock_study.yaml --out runs/study
python -m apertus_eval_prep platform-study-analyze \
    --study-config configs/studies/phase8_mock_study.yaml \
    --runs runs/study/<run_a> runs/study/<run_b> \
    --out reports/study
```

## 18. Final portfolio description

> Built a reproducible LLM evaluation and release-readiness platform that measures model
> quality, variance, RAG/agent reliability, safety risk, latency, cost, and failure patterns.
> It supports immutable experiment artifacts, evidence-aware reporting, offline CI, optional
> real open-weight model experiments, and human-review workflows.

## 19. Suggested version number

**1.0.0** — applied to `pyproject.toml` and recorded in `CHANGELOG.md`.

Rationale: the CLI is stable, the artifact schema is versioned, the test suite is
deterministic and offline, and the documentation now states the claim boundaries. The
appropriate bump from 0.x to 1.0.0 signals API stability, not feature completeness. A `1.0.1`
line is the right home for documentation and packaging corrections; breaking changes to the
artifact schema or CLI should wait for `2.0.0`.

## 20. Suggested GitHub release title

**Apertus Eval Prep 1.0.0 — reproducible LLM evaluation and release-readiness platform**


## 21. Suggested GitHub release notes

```markdown
Apertus Eval Prep 1.0.0

A reproducible LLM evaluation and release-readiness platform for measuring
capability, reliability, safety, RAG/agent behavior, latency, cost, deployment
trade-offs, and failure patterns under declared experimental conditions.

Why: a single benchmark score hides prompt sensitivity, seed and decode variance,
backend and quantization effects, RAG/agent failures, groundedness regressions, and
latency/cost trade-offs. This platform makes the evaluation configuration part of
the claim.

What is in it
- Immutable run artifacts: manifest, resolved config, dataset lock, content hashes,
  per-example outcomes, confidence intervals, gate report, failure fingerprints.
- Machine-checked evidence modes (MOCK, SYNTHETIC, LOCAL_REAL_MODEL,
  EXTERNAL_PROVIDER, HARDWARE_MEASURED, HUMAN_VALIDATED, MIXED, UNKNOWN) that refuse
  contradictory declarations.
- Variance and statistics: deterministic factor matrices, bootstrap and Wilson
  intervals, paired decisions with practical-effect thresholds, Kendall tau,
  Evaluation Reliability Score, and an experimental Robust Capability Score.
- RAG and agent episode evaluation; safety red-team suite with a declared taxonomy.
- Deployment comparison: latency/cost points, Pareto frontier, constraint selection,
  and release gates whose output states that they are not production approval.
- Evidence-aware Markdown and HTML reporting that escapes dynamic content and renders
  missing evidence as unavailable rather than zero.
- Study workflow with preregistration and deviation templates; human-review export,
  strict validation, and agreement analysis.
- Offline deterministic CI: 383 tests, CPU-only, no network, no API keys, one
  runtime dependency (pyyaml).
- Optional real open-weight model experiments, including gated-repository
  authentication validated against an authenticated endpoint.

Evidence boundaries (please read before quoting numbers)
- Mock evidence validates the framework, not any model.
- Real-model evidence is experimental and specific to its recorded model revision,
  tokenizer, dataset, prompt, decoding, backend, precision, and hardware.
- Latency measured on Colab or local hardware is not production serving latency.
- Release gates are a policy aid, not production approval. Safety suites are not
  safety certifications.
- No completed human-review artifacts are included, so no human-validation claim is
  made.
- This is a software and framework release, not a certified production system.

Known limitations are documented in docs/FINAL_AUDIT.md, including the protocol
artefact whereby core scores partly measure terse format compliance because no chat
template is applied.

Docs: README.md, docs/CLI_REFERENCE.md, docs/FAQ.md, docs/FINAL_AUDIT.md,
docs/FINAL_RELEASE_REPORT.md.

Licensed under Apache-2.0. Please read SECURITY.md before reporting a vulnerability.
```

## 22. Closing statement

**No Phase 10 is planned. This document closes the planned platform implementation.**

| `UNKNOWN` | Safe default for unrecognized provenance | nothing; flagged for follow-up |
