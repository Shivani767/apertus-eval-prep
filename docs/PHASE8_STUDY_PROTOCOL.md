# Phase 8 experimental study protocol

## Research question

Under the recorded experimental conditions, how stable are LLM quality, safety, groundedness, latency, and cost across prompt, decoding, model, backend, and quantization conditions?

## Hypotheses

- **H1:** model rankings may change across valid prompt and deployment conditions.
- **H2:** higher mean quality does not necessarily imply lower variance or better Robust Capability Score.
- **H3:** quality changes can trade off against latency, cost, groundedness, or safety.
- **H4:** aggregate scores can conceal condition-sensitive failure modes.

These are hypotheses, not established claims. They require compatible artifacts, declared evidence, and an appropriate sample.

## Scope

English-first evaluation of open-weight local models or user-authorized endpoints. The initial study should be small but reproducible, with 2–3 model/configuration candidates, 2–3 conditions per candidate, three seeds where supported, 50–100 core examples, 15–25 groundedness/RAG examples, 10–20 tool episodes, and a sanitized safety suite. Google Colab is optional experimental infrastructure, not production infrastructure.

## Controlled variables

Record model and tokenizer IDs/revisions, hardware/runtime, backend, dtype, quantization, prompt ID/version/hash, decoding settings, seed, dataset/task version/hash, code commit, pricing configuration, warm-up policy, and measurement timestamp. Missing values remain unavailable.

## Analysis

Use aggregate statistics, confidence intervals, aligned baseline/candidate comparisons, practical-effect thresholds, sample counts, explicit missing-data accounting, and timeout/error treatment. RCS is experimental. Do not interpret observational differences as causal. Label findings inconclusive when identities, evidence, or sample sizes are inadequate.

## Threats to validity

Benchmark/task overfitting, evaluator and LLM-judge bias, prompt-selection bias, seed instability, Colab/hardware variation, small samples, synthetic safety/RAG limits, manual pricing assumptions, incomplete failure fingerprints, and non-production serving conditions.

## Safe reporting language

Use: “Under the recorded experimental conditions…”, “This finding is limited to the evaluated task suite and configuration.”, “No production safety or deployment approval is implied.”, and “Results should not be generalized beyond the declared runtime and model revision.”

Do not claim a model was run without an artifact that records the execution. Do not call synthetic fixtures benchmark results or human validation.
