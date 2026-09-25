# Human review protocol

Human review is optional and privacy-safe. It is not automatic and is not implied by a review template, mock annotation, failed-case excerpt, or an evidence mode string.

## Scope

Reviewers assess only sanitized examples exported from immutable run artifacts. Reviewers should not receive private datasets, credentials, raw secrets, unnecessary personal data, or unsafe raw content. Keep reviewer identity as an anonymous hash. Do not place personal data in notes.

## Sampling

Use deterministic random, stratified, or priority sampling. Prefer a balanced pass/fail sample, oversample safety-critical and condition-sensitive failures, and include baseline/candidate disagreements when available. Record the sample size, seed, strategy, dimensions, rubric version, and run references.

## Dimensions

Correctness, instruction-following, groundedness, citation/source support, helpfulness, safe behavior, false refusal, tool-use correctness, and overall preference. Use `INSUFFICIENT_EVIDENCE` when the artifact does not support a judgment.

## Completion and adjudication

A completed annotation requires a valid label, numeric score when applicable, confidence, anonymous reviewer hash, timestamp, and evidence references. Duplicate IDs, invalid labels, mixed rubric versions, and missing identifiers are rejected. Disagreements enter an adjudication queue.

## Evidence integration

Only valid completed annotations can contribute to a human-review summary. Template-only packages, empty packages, synthetic-only annotations, and unlinked files leave `human_reviewed=false`. Agreement measures consistency, not correctness or safety validity. Human validation does not imply production approval.
