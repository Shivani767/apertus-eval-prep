# Extending the platform

## Add an adapter

Implement `ModelAdapter.complete(CompletionRequest) -> AdapterResponse`, declare capabilities, and add construction to `adapters/factory.py`. Return usage/latency only when measured or clearly label estimates. Never log credentials.

## Add a task

Implement `Task.metadata_for()` and `Task.score()` or add a typed episode schema. Validate IDs, prompts, gold labels, dimensions, and filters at load time. Add deterministic normal, invalid, timeout, and edge-case fixtures.

## Add an evaluator

An evaluator should consume per-example records, return a typed/JSON-safe result, preserve sample counts, distinguish missing from zero, and document heuristic limitations. Add focused unit tests plus a cross-module integration test.

## Add a report-safe failure record

Use `normalize_failure_record` for new failure producers. Keep raw observations in the retention-controlled artifacts, put only sanitized excerpts or references in derived records, and test credential redaction plus HTML escaping. Extend `FAILURE_CATEGORIES` only with a documented observed failure mode; do not infer causal labels from correlations.

## Add a gate


## Add a study or human-review dimension

Study configuration changes belong in `study/schema.py` and should preserve evidence-mode, identity, and placeholder validation. Review dimensions and labels belong in `review/schema.py`; never accept raw reviewer identifiers or unmarked human-review claims. Add deterministic sampling/ingestion/agreement tests, sanitized fixtures, and a report assertion. See `docs/PHASE8_STUDY_PROTOCOL.md`, `docs/HUMAN_REVIEW_PROTOCOL.md`, and `docs/ANNOTATION_GUIDELINES.md`.

Put thresholds and category weights in YAML. Test status precedence and missing-evidence behavior. A gate should be auditable, versioned, and safe to run offline in CI.
