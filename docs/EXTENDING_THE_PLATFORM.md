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

## Add a stability or selection analysis

Stability analyses in this platform are **derived** from already-committed measurements. They must never run a model, invent a cell, or fill a missing score. Read `docs/DECISION_STABILITY.md` and `docs/RANKING_STABILITY.md` first; they fix the conventions that matter:

- Reuse `stats.rank_high_is_better`, `stats.pairwise_reversals`, `stats.kendall_tau_b`, `stats.holm_bonferroni` and `metrics.pareto.select_configurations` rather than re-deriving them. One definition of a rank, one definition of a constraint.
- Report the denominator rule in the artifact. A rate whose denominator is implicit cannot be audited, and the denominator choice decides the number.
- A missing measurement is `insufficient_evidence`, never `0`. Exclude the configuration and list it with a reason.
- Refuse to emit a number when the design cannot support it: return `status: insufficient_design` with an explanation rather than a misleading value.
- Do not collapse disagreeing metrics into a composite score. Kendall tau and top-1 agreement can disagree in exactly the cases worth reading.
- Attribution to a factor is an **association** plus a design-quality label (`single_factor`, `multi_factor_confounded`, ...). Never emit a causal claim.
- Keep the policy in data, not code, and attach an evidence record with `normalize_evidence` so the tier is never inferred upward.

A new analysis should ship with: a module, a CLI subcommand following the `heldout` / `ers` naming, deterministic fixtures, tests covering the same-decision, reversal, invalid-input, missing-metric, evidence-tier and artifact-determinism cases, and a doc section stating what it does not claim.

## Add an agent metric or scenario

Agent reliability lives in `agent_reliability.py`; episode execution is unchanged. See `docs/AGENT_EVALUATION.md`. Conventions:

- A metric absent from a run is `None` or `not_comparable`, never `0`. An absent metric must not be able to satisfy a regression gate.
- Every metric declares its direction. Anything where "up" is worse -- latency, tokens, unsafe actions -- belongs in `LOWER_IS_BETTER`, or a regression will be scored as an improvement.
- Scenario classes are validated against `SCENARIO_CLASSES` and `applies` is mandatory, so a non-applicable class is excluded from the denominators rather than reading as a coverage gap.
- Coverage counts stay split: declared, executed and succeeded answer different questions and must not be collapsed into one number.
- Gate verdicts are `PASS` / `FAIL` / `INCONCLUSIVE`, and the artifact says `result_type: "policy gate result"`. Never emit approval language.
