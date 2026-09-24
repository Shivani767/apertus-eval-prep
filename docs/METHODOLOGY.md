# Methodology

## Evidence classes

`MOCK` and `DEMONSTRATION` are synthetic pipeline evidence. `MEASURED` means a real execution was recorded. `HUMAN_VALIDATED` requires a documented human-label process. `PROJECT_METRIC` denotes an explicitly non-standard metric such as RCS. Evidence class is carried into manifests and reports.

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

Fixtures are small and synthetic. Heuristics do not establish factuality, legal/medical suitability, or safety certification. High-impact decisions require representative data, human review, threat modeling, and real deployment measurements.
