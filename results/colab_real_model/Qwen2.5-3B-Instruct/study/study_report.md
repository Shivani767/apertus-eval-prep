# Phase 8 Experimental Study Report

- Study: `sarvam_application_real_eval_v1`
- Title: Phase 8 study
- Evidence: `LOCAL_REAL_MODEL`
> Experimental real-model evidence; not production approval.

## Study design and provenance

- Research question: How do real LLM configurations differ in English task quality, robustness across valid inference conditions, RAG/agent reliability, sanitized safety behavior, latency, cost estimates, and failure profiles?
- Hypotheses: `H1, H2, H3, H4`
- Planned samples: `{'core': 38, 'rag': 5, 'agent': 5, 'safety': 11, 'review': 30}`
- Protocol: `docs/PHASE8_STUDY_PROTOCOL.md`
- Preregistration: `docs/studies/SARVAM_APPLICATION_REAL_STUDY_PREREGISTRATION.md`
- Deviations: `NOT_ASSESSED`

## Model/configuration summary

| Run | Model/revision | Evidence | Config hash | Quality | 95% CI |
|---|---|---|---|---:|---|
| `20260926T131836550716Z-sarvam-application-local-variance-baseli-6bf9e8ff` | `Qwen/Qwen2.5-3B-Instruct` / `main` | `LOCAL_REAL_MODEL` | `3895d1804914d5cd` | 0.4737 | [0.3158, 0.6316] |
| `20260926T132044255178Z-sarvam-application-local-variance-backen-1f3012ef` | `Qwen/Qwen2.5-3B-Instruct` / `main` | `LOCAL_REAL_MODEL` | `72eb4148726bd17b` | 0.4737 | [0.3158, 0.6316] |
| `20260926T132303074687Z-sarvam-application-local-variance-backen-00f7aaa1` | `Qwen/Qwen2.5-3B-Instruct` / `main` | `LOCAL_REAL_MODEL` | `3591df72ccaefee7` | 0.4737 | [0.3158, 0.6316] |

## Comparisons

- `20260926T131836550716Z-sarvam-application-local-variance-baseli-6bf9e8ff` → `20260926T132044255178Z-sarvam-application-local-variance-backen-1f3012ef`: delta `0.0000`, 95% CI `[0.0000, 0.0000]`, effect `unavailable`, status **NO_MEANINGFUL_CHANGE**, practically meaningful: `False`.
- `20260926T131836550716Z-sarvam-application-local-variance-baseli-6bf9e8ff` → `20260926T132303074687Z-sarvam-application-local-variance-backen-00f7aaa1`: delta `0.0000`, 95% CI `[0.0000, 0.0000]`, effect `unavailable`, status **NO_MEANINGFUL_CHANGE**, practically meaningful: `False`.

## Experimental Robust Capability Score

- Mean quality: `0.4737`
- Configuration variance: `0.0000`
- Lambda: `1.0000`
- RCS: `0.4737`
- Experimental: `True`

## Safety, RAG/agent, and deployment

- `20260926T131836550716Z-sarvam-application-local-variance-baseli-6bf9e8ff`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `7252.3346`, cost/success `unavailable`, gate `INCONCLUSIVE`.
- `20260926T132044255178Z-sarvam-application-local-variance-backen-1f3012ef`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `13219.9806`, cost/success `unavailable`, gate `INCONCLUSIVE`.
- `20260926T132303074687Z-sarvam-application-local-variance-backen-00f7aaa1`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `8022.0697`, cost/success `unavailable`, gate `INCONCLUSIVE`.

## Pareto frontier

- Pareto-optimal: `0`
- Dominated: `0`
- Excluded/inconclusive: `3`

## Failure fingerprints

- `20260926T131836550716Z-sarvam-application-local-variance-baseli-6bf9e8ff`: failures `20`, rate `0.5263`, priority `P0`.
- `20260926T132044255178Z-sarvam-application-local-variance-backen-1f3012ef`: failures `20`, rate `0.5263`, priority `P0`.
- `20260926T132303074687Z-sarvam-application-local-variance-backen-00f7aaa1`: failures `20`, rate `0.5263`, priority `P0`.

## Human review

- Status: `NOT_PROVIDED`
- Human reviewed: `False`

## Missing evidence / inconclusive results

- 20260926T131836550716Z-sarvam-application-local-variance-baseli-6bf9e8ff: safety suite unavailable
- 20260926T131836550716Z-sarvam-application-local-variance-baseli-6bf9e8ff: RAG/agent suite unavailable
- 20260926T131836550716Z-sarvam-application-local-variance-baseli-6bf9e8ff: cost per successful task unavailable
- 20260926T132044255178Z-sarvam-application-local-variance-backen-1f3012ef: safety suite unavailable
- 20260926T132044255178Z-sarvam-application-local-variance-backen-1f3012ef: RAG/agent suite unavailable
- 20260926T132044255178Z-sarvam-application-local-variance-backen-1f3012ef: cost per successful task unavailable
- 20260926T132303074687Z-sarvam-application-local-variance-backen-00f7aaa1: safety suite unavailable
- 20260926T132303074687Z-sarvam-application-local-variance-backen-00f7aaa1: RAG/agent suite unavailable
- 20260926T132303074687Z-sarvam-application-local-variance-backen-00f7aaa1: cost per successful task unavailable

## Limitations

- No causal conclusions are drawn from observed configuration differences.
- RCS is experimental and is not a standard universal metric.
- Human-review agreement measures consistency, not correctness or safety validity.

## Reproducibility

Underlying run IDs, config hashes, dataset hashes, prompt hashes, and artifact paths are preserved in `study_summary.json` and `comparison_table.csv`.
