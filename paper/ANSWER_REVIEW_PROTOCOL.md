# Blinded answer-extraction review — proposed, not completed

Status: **NEEDS EXPERIMENTS**. Exporting a packet does not validate the scorer or change any paper result.

## Scope and export

The exporter selects the same random items per task across Qwen2.5-3B and Phi-3.5-mini, control and five-shot. Selection does not condition on correctness or disagreement. All four frozen task slices are included. The default 20 items per task is a pilot workload, not a power calculation or a sufficient validation sample. Repeated outputs for the same question are paired, not independent observations.

From the repository root, invoke `python scripts/export_answer_review.py --out /tmp/apertus-answer-review --per-task 20 --seed 0` with the configured project interpreter. The destination must not already exist: this prevents accidental overwriting of annotations. This local-output command is not part of `make paper`.

- Give reviewers only `reviewer.jsonl` and this protocol.
- Keep `PRIVATE_key.json` inaccessible to reviewers. It contains model/configuration labels, item IDs, gold answers, saved predictions/correctness, selected IDs and source hashes. Restrictive file permissions are not a substitute for separate access control.
- Review IDs are opaque random identifiers. Sampling is seed-reproducible, but identifiers are intentionally not reproducible from the public seed. Retain the private key.
- Raw generations are unchanged, including empty outputs. They may reveal model identity or prompt style; metadata blinding is not perfect blinding. Reviewers should record suspected unblinding in notes.
- Questions use the frozen benchmark text, not a reconstructed historical full prompt. The review addresses intended-answer extraction, not instruction compliance.

## Annotation, before unblinding

Use two reviewers working independently; make separate copies of the same packet. Reviewers should not inspect repository results or the private key. For each record fill:

1. `answer_status`: one of `answer`, `ambiguous`, `no_answer`, `empty`, `uninterpretable`.
2. `intended_answer`: explicit intended final answer; use an option letter for multiple choice, a numeric string for math. Leave blank for non-answer categories. Do not solve the question and substitute the correct answer when the generation gives another answer.
3. `notes`: final-answer evidence, contradictions, locale/format ambiguity, truncation or suspected unblinding.

An answer can be clearly expressed and mathematically wrong: answer extraction is not correctness grading. Do not assign correctness labels before gold is revealed. Do not invent a final answer for truncated reasoning. Empty means whitespace-only generation; runtime/timeout cannot be inferred from text alone. Resolve reviewer disagreements through a documented third adjudication before unblinding; preserve original annotations.

## Analysis plan to freeze before annotation

Predeclare numeric normalization and treatment of ambiguity before examining labels. Report review completion and inter-reviewer disagreement by task. After adjudication, join by review ID to compare human-extracted answers with saved predictions; retain ambiguous/non-answer cases in the denominator and report them separately. Report parser agreement, false-credit and missed-credit counts by model/configuration/task. Report reviewed-sample ranking sensitivity, not an extrapolated full-matrix replacement score.

Any confidence intervals must respect shared-question grouping across outputs and related translated questions; recover semantic source groups before general population inference. Small task-stratified pilots are diagnostic, not confirmation of ranking robustness. Do not retrofit parsing rules to maximize a model's score; develop rules on separate material and validate on held-out items. Completing this review does not resolve missing model revisions or historical software drift.

## Handling and preservation

Snapshots and generations may carry redistribution restrictions. Keep packets local pending the licensing review; do not add private keys or completed reviewer annotations to a public source bundle automatically. Archive protocol version, source hashes, reviewer identities/consent, annotation timestamps, disagreement resolution, and analysis code after actual review. No human annotation or adjudication has yet been claimed.
