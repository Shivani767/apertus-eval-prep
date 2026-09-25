# Technical study plan: Sarvam application real evaluation

**Status:** preparation template; no real model has been executed in this document.

## Research question

How do real LLM configurations differ in English task quality, robustness across valid inference conditions, RAG/agent reliability, sanitized safety behavior, latency, cost estimates, and failure profiles?

## Evidence boundary

This plan separates deterministic framework validation (`MOCK`) from experimental real-model evidence (`LOCAL_REAL_MODEL`), external-provider evidence (`EXTERNAL_PROVIDER`), and human-reviewed evidence. A `MOCK` result can validate the harness but cannot support a model-quality or safety claim. No real-model, GPU, download, Colab, provider, or paid API execution is part of this preparation step.

## Planned candidates

- Local/open-weight candidate IDs: `YOUR_MODEL_ID_1`, `YOUR_MODEL_ID_2` (replace privately).
- Optional provider candidate: `EXTERNAL_PROVIDER_MODEL_ID` only if explicitly authorized.
- Revisions/tokenizer revisions: `OPTIONAL_PINNED_REVISION` / `YOUR_PINNED_REVISION`.
- Hardware/runtime: `REPLACE_WITH_DECLARED_RUNTIME`.
- Investigator: `REPLACE_WITH_INVESTIGATOR`.
- Execution date: `REPLACE_WITH_DATE`.
- Manual pricing: `REPLACE_WITH_VERSIONED_PRICING_OR_UNAVAILABLE`.

## Hypotheses

- **H1:** Rankings may change across valid prompt and deployment conditions.
- **H2:** Higher mean quality need not imply lower configuration variance or higher experimental RCS.
- **H3:** Quality may trade off against latency, cost, groundedness, or safety.
- **H4:** Aggregate scores may conceal condition-sensitive failure modes.

## Primary and secondary metrics

Primary: quality/task score with paired uncertainty and failure rate. Secondary: groundedness, RAG/agent completion and tool validity, sanitized safety/risk, latency, tokens, cost per successful task, throughput, and failure-fingerprint categories. RCS is reported only as an experimental project-defined score.

## Scope and sample plan

English-first primary scope: 40 core examples from the existing English task subset; 15 RAG and 15 agent episodes; up to 20 sanitized safety cases; optional 30-item human-review sample. The India-context diagnostic is exploratory, separately reported, and capped at 12 examples.

## Controlled variables

Record model/tokenizer ID and revision, adapter/backend, device, dtype, quantization, trust-remote-code choice, prompt ID/version/hash, decoding settings, seed, dataset/task identity and hash, code commit, warm-up/timing boundary, runtime profile, hardware identity, manual pricing source/date, and measurement date.

## Analysis plan

Use aligned paired comparisons, confidence intervals, effect size when defined, configurable practical-effect thresholds, sample-size checks, and explicit treatment of timeouts/errors as missing or infrastructure evidence where appropriate. Use RCS as an exploratory sensitivity analysis, not a universal metric. Do not make causal claims from configuration observations. Label underpowered, sparse, mixed, or incompatible evidence `INCONCLUSIVE`.

## Warm-up and timing

Run warm-up separately from measured examples. Record client-side wall-clock latency around the declared adapter operation, and do not include setup/download time unless explicitly labelled. Record token counts only when the backend reports them; keep cost unavailable when tokens or prices are missing.

## Exclusion and stopping rules

Exclude malformed or unauthorized data, failed provenance, duplicate IDs, and incompatible task/prompt/metric identities. Preserve failures and explain exclusions. Stop and report `INCONCLUSIVE` if real runs fail provenance, compatibility, sample-count, or artifact-integrity requirements.

## Human review

Export a sanitized stratified/priority sample, use anonymous hashed reviewer IDs, one rubric version, two reviewers where possible, disagreement adjudication, and agreement metrics. Templates and empty packages are not human evidence. A completed real linked annotation set is required before setting `human_reviewed: true`.

## Safety boundary

The safety suite contains sanitized, abstract cases only. It does not measure real-world attack prevalence or certify safety. High-impact conclusions require representative data, approved threat modeling, privacy/security review, monitoring, and accountable human review.

## Deviations and reporting

Record deviations in the deviation log before interpreting results. Use wording such as “Under the recorded experimental conditions…” and “Results should not be generalized beyond the declared runtime and model revision.” Release gates are engineering policy aids, not production approval.
