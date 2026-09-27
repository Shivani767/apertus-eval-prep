# Changelog

All notable changes to Apertus Eval Prep are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**What this project is:** a reproducible LLM evaluation and release-readiness *framework*.
The entries below describe software capabilities. They do **not** assert model rankings,
safety certification, or production approval. Numbers quoted in `results/` are
condition-specific and carry an evidence mode; see
[Evidence and Claim Boundaries](docs/METHODOLOGY.md#evidence-and-claim-boundaries).

## [Unreleased]

Nothing pending.

## [1.0.0] - 2026-09-27

First stable release. Phases 1–9.

### Added — provenance and configuration (Phase 1)

- Typed, versioned run specification: adapter, task, prompt, decoding, metrics, reporting
  declared in YAML, with a resolved config written alongside every run.
- Immutable run directories containing `manifest.json`, `config.resolved.yaml`,
  `dataset.lock.json`, `metrics.json`, `confidence_intervals.json`, `gate_report.json`,
  `failures.jsonl`, `failure_fingerprint.json`, `scored_examples.jsonl`, `raw_outputs.jsonl`,
  and Markdown/HTML reports.
- Machine-checked evidence modes (`MOCK`, `SYNTHETIC`, `LOCAL_REAL_MODEL`,
  `EXTERNAL_PROVIDER`, `HARDWARE_MEASURED`, `HUMAN_VALIDATED`, `MIXED`, `UNKNOWN`) with
  consistency validation that refuses contradictory manifests.
- Identity checks that refuse to compare or aggregate runs whose dataset, task, prompt, or
  metric identity differs.

### Added — variance and statistics (Phase 2)

- Deterministic experiment matrices expanding declared factors (seeds, prompt templates,
  decoding, backend, dtype, quantization) with per-cell artifacts.
- Bootstrap confidence intervals, Wilson intervals, paired deltas with practical-effect
  thresholds, and Kendall rank correlation.
- Evaluation Reliability Score and the experimental Robust Capability Score
  (`RCS = mean_quality − λ · configuration_variance`), always reported with both components
  and labelled experimental.

### Added — RAG and agent evaluation (Phase 3)

- Episode-level evaluation with tool traces, retrieval groundedness, turn budgets, and
  outcome classification for RAG and agent workflows.

### Added — safety evaluation (Phase 4)

- Sanitized offline safety suite with an explicit failure-category taxonomy, severity
  weighting, attack-success and false-refusal metrics.
- Automated red-team evaluation over declared categories. **Not** a safety certification.

### Added — deployment metrics and release gates (Phase 5)

- Latency, cost, and quality comparison points; Pareto frontier; constraint-based
  selection with explicit `insufficient_evidence` states.
- Release-gate policy evaluation whose output carries a non-approval disclaimer.

### Added — reporting (Phase 6)

- Evidence-aware Markdown and HTML reports that escape dynamic content, render the evidence
  label, and preserve missing evidence as unavailable rather than zero.
- Failure fingerprints: stable, prompt-identity-independent failure grouping with
  investigation priorities that are explicitly a triage aid, not causal claims.

### Added — real-model evidence (Phase 7)

- Optional local/open-weight adapters behind the `real-model` extra, imported lazily so the
  offline path needs no GPU runtime.
- Colab workflow: one generated notebook per model, gated-repository authentication
  (`apertus_eval_prep.hub_auth`), Drive mirroring, export and ingestion of real runs.
- Curated real-run evidence under `results/colab_real_model/`, with failed attempts recorded
  separately under `results/colab_failed_runs/` so they cannot be mistaken for results.



### Added — study and human-review workflow (Phase 8)

- Study configuration, preregistration template, protocol, and deviation-log templates.
- `platform-study-analyze` aggregating compatible completed runs, recording the evidence
  modes present and whether real-model evidence is available.
- `platform-export-review` / `platform-ingest-review`: sanitized review packages, strict
  validation that rejects incomplete annotations, and agreement analysis. Agreement measures
  annotator consistency, not correctness or safety.
- Human-review protocol and annotation guidelines.

### Added — final audit and release (Phase 9)

- `docs/FINAL_AUDIT.md` and `docs/FINAL_RELEASE_REPORT.md`.
- Release packaging: `CHANGELOG.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`,
  `docs/RELEASE_CHECKLIST.md`, `docs/SECURITY_AND_PRIVACY.md`, `docs/FAQ.md`, and a
  `docs/CLI_REFERENCE.md` verified against the live CLI.
- Central "Evidence and Claim Boundaries" sections in `README.md` and `docs/METHODOLOGY.md`,
  distinguishing framework validation, experimental real-model evaluation, human-reviewed
  evidence, and production validation.
- Repository hygiene: duplicate root-level files removed, `.gitignore` corrected (duplicate
  and misplaced patterns, added SSH-key and coverage artifacts), and README badges corrected
  to match the actual test count and the Apache-2.0 license.

### Fixed

- Adapter load failures now carry a redacted, bounded underlying cause, so a 401 from a
  gated repository is distinguishable from a wrong revision or a missing optional package.
- Artifact redaction recognises `hf_`-prefixed Hugging Face credentials.
- Gated-model preflight validates the token against an authenticated endpoint and probes the
  actual download, instead of trusting public repository metadata and any ambient token.
  Three earlier runs failed all 257 examples because the preflight reported success while
  every download returned 401; the fix is covered by `tests/test_hub_auth.py`.
- Real-model notebooks delegate authentication to the tested module; the template is the
  single source of truth and the generator propagates it.

### Notes on evidence

- `results/colab_real_model/` contains seven models with preserved real run artifacts.
  `results/colab_failed_runs/` contains recorded attempts that produced no usable
  measurement; they are excluded from every comparison.
- The research-harness artifacts under `results/` predate the typed platform and carry no
  evidence-mode field. They are legacy research artifacts, not platform evidence.
- No completed human-review artifacts are included, so no human-validation claim is made.

[Unreleased]: https://github.com/Shivani767/apertus-eval-prep/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Shivani767/apertus-eval-prep/releases/tag/v1.0.0
