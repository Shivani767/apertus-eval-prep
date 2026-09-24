# Real evaluation protocol

This protocol distinguishes framework validation from real-model, hardware, human, and production evidence. Passing a release gate is not production approval.

## Evidence levels

1. **Framework validation** — deterministic `MOCK`/`SYNTHETIC` fixtures verify the platform and reports. It is not model evidence.
2. **Experimental real-model validation** — a declared local/Colab runtime executes a pinned model and records client-side measurements. It is not production approval.
3. **Hardware benchmark** — a controlled, declared environment measures performance on specified hardware. Record allocation/runtime identity and repeat the run.
4. **Human-validated evaluation** — a documented reviewer protocol, rubric, reviewer identity policy, disagreement handling, and adjudication produce labels.
5. **Production validation** — organizational release review adds representative data, monitoring, security/privacy review, incident response, operational controls, and accountable human approval.

`HARDWARE_MEASURED`, `HUMAN_VALIDATED`, and `MIXED` must be declared explicitly. Legacy artifacts without an evidence block are inferred conservatively as `MOCK`, `SYNTHETIC`, `HUMAN_VALIDATED`, or `UNKNOWN`; an old `MEASURED` label alone is not promoted to a new evidence mode.

## Reproducibility requirements

1. Pin the model revision and tokenizer revision whenever the source supports immutable revisions.
2. Record model/tokenizer IDs, adapter/backend, device, dtype, quantization, trust-remote-code choice, seed, and complete decoding settings.
3. Record dataset bytes/path hash, task identity/hash, prompt ID/version/hash, metric definition version, and resolved config hash.
4. Keep the task, prompt, metric definition, and evidence mode identical when comparing configurations. `platform-ingest-runs` rejects incompatible identities.
5. Separate warm-up from timed examples. Do not include model download, notebook setup, or first-call compilation in example latency unless explicitly labelled.
6. Repeat seeds and deployment-relevant conditions. A single greedy run does not measure sampling/deployment variance.
7. Record runtime environment, OS/platform, Python, Torch, CUDA, GPU name/count/memory, and latency method. Unavailable facts stay unavailable.
8. State exactly what latency means. The local adapter measures client-side wall-clock around tokenization, model generation, and decoding; it is not a production-serving metric.
9. Preserve token counts only when measured or explicitly estimated by a documented backend method. Cost requires both usable token counts and user-provided prices.
10. Store price input/output values, currency, source, effective date, and estimate label. Do not retrieve or embed current provider prices.
11. Preserve `manifest.json`, resolved config, dataset lock, raw/scored records, metrics, confidence intervals, gate/failure reports, and report files.
12. Treat release gates as engineering policy aids. Do not describe Colab results as production benchmarks.

## Hardware benchmark controls

A hardware claim requires declared hardware/runtime identity, warm-up policy, number of repeated trials, exact timing boundary, token usage, failure accounting, and uncertainty. Allocate hardware may vary; record every session rather than assuming a requested GPU was assigned. If hardware facts cannot be measured, mark them unavailable.

## Safety and human review

Sanitized fixtures test harness behavior, not real-world prevalence. High-impact decisions need approved representative/adversarial data, privacy/security review, human review, monitoring, and incident response. Never place sensitive prompts, private context, secrets, or unsafe raw outputs in public notebooks or fixtures.

## Security

- Never commit tokens, API keys, passwords, cookies, or private dataset content.
- Prefer environment variables or notebook-secret mechanisms in private workflows.
- Keep `trust_remote_code` false unless an approved model explicitly requires it.
- Do not commit downloaded caches/weights or large generated runs.
- Retain raw outputs only when policy allows; artifact/report writers redact credentials and PII patterns.
- Curate any public case-study report manually and review licensing/privacy before committing it.
