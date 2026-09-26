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
| `20260926T151520286459Z-sarvam-application-local-variance-baseli-8f500dc7` | `google/gemma-2-2b-it` / `main` | `LOCAL_REAL_MODEL` | `ba20283c3ee4f28a` | unavailable | [unavailable, unavailable] |
| `20260926T151546442104Z-sarvam-application-local-variance-backen-cc1b4f86` | `google/gemma-2-2b-it` / `main` | `LOCAL_REAL_MODEL` | `43a58048a68e1d4b` | unavailable | [unavailable, unavailable] |
| `20260926T151605306880Z-sarvam-application-local-variance-backen-1ad481ad` | `google/gemma-2-2b-it` / `main` | `LOCAL_REAL_MODEL` | `878c1700d084b9f1` | unavailable | [unavailable, unavailable] |

## Comparisons

- `20260926T151520286459Z-sarvam-application-local-variance-baseli-8f500dc7` → `20260926T151546442104Z-sarvam-application-local-variance-backen-cc1b4f86`: delta `unavailable`, 95% CI `[unavailable, unavailable]`, effect `unavailable`, status **INCONCLUSIVE**, practically meaningful: `False`.
- `20260926T151520286459Z-sarvam-application-local-variance-baseli-8f500dc7` → `20260926T151605306880Z-sarvam-application-local-variance-backen-1ad481ad`: delta `unavailable`, 95% CI `[unavailable, unavailable]`, effect `unavailable`, status **INCONCLUSIVE**, practically meaningful: `False`.

## Experimental Robust Capability Score

- Mean quality: `unavailable`
- Configuration variance: `unavailable`
- Lambda: `1.0000`
- RCS: `unavailable`
- Experimental: `True`

## Safety, RAG/agent, and deployment

- `20260926T151520286459Z-sarvam-application-local-variance-baseli-8f500dc7`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `unavailable`, cost/success `unavailable`, gate `INCONCLUSIVE`.
- `20260926T151546442104Z-sarvam-application-local-variance-backen-cc1b4f86`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `unavailable`, cost/success `unavailable`, gate `INCONCLUSIVE`.
- `20260926T151605306880Z-sarvam-application-local-variance-backen-1ad481ad`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `unavailable`, cost/success `unavailable`, gate `INCONCLUSIVE`.

## Pareto frontier

- Pareto-optimal: `0`
- Dominated: `0`
- Excluded/inconclusive: `3`

## Failure fingerprints

- `20260926T151520286459Z-sarvam-application-local-variance-baseli-8f500dc7`: failures `38`, rate `1.0000`, priority `P0`.
- `20260926T151546442104Z-sarvam-application-local-variance-backen-cc1b4f86`: failures `38`, rate `1.0000`, priority `P0`.
- `20260926T151605306880Z-sarvam-application-local-variance-backen-1ad481ad`: failures `38`, rate `1.0000`, priority `P0`.

## Human review

- Status: `NOT_PROVIDED`
- Human reviewed: `False`

## Missing evidence / inconclusive results

- 20260926T151520286459Z-sarvam-application-local-variance-baseli-8f500dc7: safety suite unavailable
- 20260926T151520286459Z-sarvam-application-local-variance-baseli-8f500dc7: RAG/agent suite unavailable
- 20260926T151520286459Z-sarvam-application-local-variance-baseli-8f500dc7: cost per successful task unavailable
- 20260926T151546442104Z-sarvam-application-local-variance-backen-cc1b4f86: safety suite unavailable
- 20260926T151546442104Z-sarvam-application-local-variance-backen-cc1b4f86: RAG/agent suite unavailable
- 20260926T151546442104Z-sarvam-application-local-variance-backen-cc1b4f86: cost per successful task unavailable
- 20260926T151605306880Z-sarvam-application-local-variance-backen-1ad481ad: safety suite unavailable
- 20260926T151605306880Z-sarvam-application-local-variance-backen-1ad481ad: RAG/agent suite unavailable
- 20260926T151605306880Z-sarvam-application-local-variance-backen-1ad481ad: cost per successful task unavailable

## Limitations

- No causal conclusions are drawn from observed configuration differences.
- RCS is experimental and is not a standard universal metric.
- Human-review agreement measures consistency, not correctness or safety validity.

## Reproducibility

Underlying run IDs, config hashes, dataset hashes, prompt hashes, and artifact paths are preserved in `study_summary.json` and `comparison_table.csv`.
