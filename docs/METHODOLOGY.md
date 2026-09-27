# Methodology

## Evidence classes

Evidence mode is a versioned, machine-checked label defined in
`src/apertus_eval_prep/core/evidence.py` and carried into every manifest and report:

| Mode | Meaning |
|---|---|
| `MOCK` | Deterministic fixture execution. Validates the framework, not a model. |
| `SYNTHETIC` | Synthetic but not mock-scaffold evidence. Still not a model measurement. |
| `LOCAL_REAL_MODEL` | Real open-weight weights executed locally. Requires `real_model_execution=true`; the code raises if that flag is absent. |
| `EXTERNAL_PROVIDER` | A hosted provider produced the responses. Requires `external_provider_execution=true`. |
| `HARDWARE_MEASURED` | Latency or throughput measured on declared hardware. Requires `hardware_measured=true`. |
| `HUMAN_VALIDATED` | Human review completed and linked. Requires `human_reviewed=true`. |
| `MIXED` | More than one mode is present in one aggregation. |
| `UNKNOWN` | Undeclared. The safe default when nothing can be proven. |

`normalize_evidence` refuses inconsistent combinations — declaring `MOCK` while also
claiming real execution raises `ValueError` rather than writing a contradictory manifest.
`infer_evidence_mode` deliberately never maps an unrecognized legacy class to a real mode;
it returns `UNKNOWN`, because under-claiming is recoverable and over-claiming is not.

Two sets group these: `SYNTHETIC_EVIDENCE_MODES` (`MOCK`, `SYNTHETIC`) and
`REAL_EVIDENCE_MODES` (`LOCAL_REAL_MODEL`, `EXTERNAL_PROVIDER`, `HARDWARE_MEASURED`,
`HUMAN_VALIDATED`).

# Evidence and Claim Boundaries

Four tiers, and a number is only as strong as the tier it came from. The full discussion is
in the [README](../README.md#evidence-and-claim-boundaries); the methodological rules are
below.

## 1. Framework validation

Deterministic mock fixtures executed offline and in CI. This tier establishes that
artifacts are written correctly, that metrics and confidence intervals are derived
correctly, that failure fingerprints group as intended, that reports render, and that
gates evaluate.

It establishes **nothing about any model.** A `MOCK` score is not a benchmark result. A
`MOCK` latency is not a hardware measurement. Fixture cost figures are **not** provider
pricing; no price is embedded in the repository, and cost is reported as unavailable unless
a caller supplies one.

## 2. Experimental real-model evaluation

Real weights under a declared configuration. A statement is supportable only for the
recorded conditions, and the manifest is what makes that checkable: model id and commit
revision, tokenizer identity, dataset and task hashes, prompt id and version, decoding
parameters, backend, dtype, quantization, and the hardware profile.

Generalizability is limited in three ways, and all three are real:

- **Configuration-bound.** A score is a property of *model + prompt + decode + backend +
  hardware + dataset*. It is not a property of the model alone, and it does not transfer to
  an unpinned `main`, a different backend, or a different prompt.
- **Sample-bound.** The curated suites are small (38 core items, 11 safety items), so
  intervals are wide and the platform reports them rather than hiding them behind a point
  estimate.
- **Protocol-bound.** The harness sends raw text and does not apply a chat template, so
  part of what a core score measures is terse format compliance rather than correctness.
  Where a model emits the right answer inside prose, its score is depressed for a reason
  unrelated to capability. Correcting this is a **protocol change** that alters
  `metric_definition_version` and requires re-running every model; it is not a reporting
  fix.

## 3. Human-reviewed evidence

Valid **only** when completed, linked annotation artifacts exist. `platform-ingest-review`
enforces this: an annotation that is not marked completed raises
`ReviewValidationError`, so an unfinished review can never be reported as agreement, and
annotations that stay synthetic keep `human_reviewed=false`.

Agreement measures **consistency between annotators, not correctness and not safety.**
High agreement on a weak rubric is a weak rubric measured consistently. The annotation
template and protocol in `docs/` are a tooling offering, not evidence that human review
happened. This repository ships no completed human-review artifacts, so it makes no
human-validation claim.

## 4. Production validation

**Not provided by this repository.** Production evidence requires organizational
governance, deployment monitoring, privacy and security review, human approval, and
application-specific testing. The platform contributes instrumentation for that process and
nothing more.

Two specific boundaries are enforced in output, not just documented:

- A **release gate** is a policy aid evaluated against thresholds this repository defines.
  The gate payload carries its own non-approval disclaimer, and a passing gate is not a
  safety certification.
- **Groundedness** is a lexical-support heuristic suitable for offline CI. It measures
  whether an answer is supported by its retrieved context; it does not measure factuality.
  Likewise, the automated safety suite is a red-team evaluation over a declared taxonomy,
  not a safety certification, and it does not generalize to categories it has not tested.

## Quality and uncertainty

Static QA uses normalized exact matching for short-answer fixtures. Every aggregate includes scored count, failed count, missing/invalid count, mean, median, standard deviation, standard error, range, and percentiles. Means can include a seeded bootstrap interval; correctness may additionally include a Wilson interval. Small samples are visible rather than hidden behind a point estimate.

## Paired decisions

The candidate-minus-baseline delta is aligned by example ID. A configurable practical-effect threshold defines meaningful change; confidence-interallel uncertainty and sample size determine the classification. Missing examples are counted. The six statuses are confirmed/likely regression or improvement, no meaningful change, and inconclusive.

## Evaluation Variance Lab

A matrix run expands declarative factors over seeds, prompt templates, decoding settings, model revision, backend, precision/quantization, task, dataset, and split. Each child writes its own immutable artifacts, records the parent experiment ID, and saves a resolved configuration. The parent report keeps overall quality statistics, per-factor means and bootstrap intervals, an aligned baseline/candidate comparison, and condition-sensitive failure classes.

The six decision statuses are based on the candidate-minus-baseline delta, a configurable practical-effect threshold, confidence information, and minimum sample size. Missing or invalid observations are counted and do not silently become zero. Stable successes/failures and prompt-, backend-, and quantization-sensitive examples are reported separately.

`RCS = mean_quality - lambda * configuration_variance` is explicitly experimental. It reports mean quality, configuration variance, lambda, sample count, and limitations. It is not a standard universal metric, is sensitive to factor design and sparse matrices, and must not replace domain-specific evaluation or human review.

## Robust Capability Score

`RCS = mean_quality - lambda * configuration_variance` is a project-defined experimental score. It is always reported with both components, lambda, sample count, and limitations. It is not a universal benchmark metric and should not replace a domain-specific evaluation.

## Groundedness, safety, and deployment

Groundedness defaults to a lexical-support heuristic for offline CI, not semantic truth. Safety metrics expose attack success, category pass rates, false refusal, severity, and weighted components. Cost and latency are measured or explicitly unavailable; no provider price is embedded. Pareto and constraint results describe evaluated configurations only.

## Failure fingerprints and review reports

Each applicable run writes `failures.jsonl` and `failure_fingerprint.json`. The fingerprint aggregates category/severity counts, observed stable and condition-sensitive failures, representative sanitized excerpts, and deterministic investigation priorities. Priorities are an observed-pattern triage aid: severity, safety relevance, failure rate, baseline delta, and condition labels contribute to the documented score; they do not establish causation.

`platform-report` rebuilds `report.md` and `report.html` from an immutable run without rerunning a model. `platform-fingerprint` rebuilds the derived diagnostic JSON. Both commands preserve missing evidence as unavailable and redact dynamic content before rendering.

## Limitations


## Study-level evidence and human review

A study aggregates only compatible run identities and records whether the available evidence is synthetic, real-model, or human-reviewed. `MOCK`/synthetic artifacts cannot establish real-model conclusions. Human-review evidence requires valid completed annotations linked to non-synthetic runs; templates and synthetic-only annotations remain `human_reviewed=false`. Agreement is a consistency diagnostic, not proof of validity, safety, or production readiness. See `docs/PHASE8_STUDY_PROTOCOL.md` and `docs/HUMAN_REVIEW_PROTOCOL.md`.

Fixtures are small and synthetic. Heuristics do not establish factuality, legal/medical suitability, or safety certification. High-impact decisions require representative data, human review, threat modeling, and real deployment measurements.
