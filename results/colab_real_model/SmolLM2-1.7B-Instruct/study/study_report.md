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
| `20260926T124648119020Z-sarvam-application-local-variance-baseli-fb5c014f` | `HuggingFaceTB/SmolLM2-1.7B-Instruct` / `main` | `LOCAL_REAL_MODEL` | `baa82c05ab9e44af` | 0.0000 | [0.0000, 0.0000] |
| `20260926T124721896487Z-sarvam-application-local-variance-backen-4bc87d65` | `HuggingFaceTB/SmolLM2-1.7B-Instruct` / `main` | `LOCAL_REAL_MODEL` | `ea771f5b97a0b575` | 0.0000 | [0.0000, 0.0000] |
| `20260926T124734097204Z-sarvam-application-local-variance-backen-17676650` | `HuggingFaceTB/SmolLM2-1.7B-Instruct` / `main` | `LOCAL_REAL_MODEL` | `ca5fb799d9c01df7` | 0.0000 | [0.0000, 0.0000] |

## Comparisons

- `20260926T124648119020Z-sarvam-application-local-variance-baseli-fb5c014f` → `20260926T124721896487Z-sarvam-application-local-variance-backen-4bc87d65`: delta `0.0000`, 95% CI `[0.0000, 0.0000]`, effect `unavailable`, status **NO_MEANINGFUL_CHANGE**, practically meaningful: `False`.
- `20260926T124648119020Z-sarvam-application-local-variance-baseli-fb5c014f` → `20260926T124734097204Z-sarvam-application-local-variance-backen-17676650`: delta `0.0000`, 95% CI `[0.0000, 0.0000]`, effect `unavailable`, status **NO_MEANINGFUL_CHANGE**, practically meaningful: `False`.

## Experimental Robust Capability Score

- Mean quality: `0.0000`
- Configuration variance: `0.0000`
- Lambda: `1.0000`
- RCS: `0.0000`
- Experimental: `True`

## Safety, RAG/agent, and deployment

- `20260926T124648119020Z-sarvam-application-local-variance-baseli-fb5c014f`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `2453.5346`, cost/success `unavailable`, gate `INCONCLUSIVE`.
- `20260926T124721896487Z-sarvam-application-local-variance-backen-4bc87d65`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `1328.7551`, cost/success `unavailable`, gate `INCONCLUSIVE`.
- `20260926T124734097204Z-sarvam-application-local-variance-backen-17676650`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `1276.4499`, cost/success `unavailable`, gate `INCONCLUSIVE`.

## Pareto frontier

- Pareto-optimal: `0`
- Dominated: `0`
- Excluded/inconclusive: `3`

## Failure fingerprints

- `20260926T124648119020Z-sarvam-application-local-variance-baseli-fb5c014f`: failures `38`, rate `1.0000`, priority `P0`.
- `20260926T124721896487Z-sarvam-application-local-variance-backen-4bc87d65`: failures `38`, rate `1.0000`, priority `P0`.
- `20260926T124734097204Z-sarvam-application-local-variance-backen-17676650`: failures `38`, rate `1.0000`, priority `P0`.

## Human review

- Status: `NOT_PROVIDED`
- Human reviewed: `False`

## Missing evidence / inconclusive results

- 20260926T124648119020Z-sarvam-application-local-variance-baseli-fb5c014f: safety suite unavailable
- 20260926T124648119020Z-sarvam-application-local-variance-baseli-fb5c014f: RAG/agent suite unavailable
- 20260926T124648119020Z-sarvam-application-local-variance-baseli-fb5c014f: cost per successful task unavailable
- 20260926T124721896487Z-sarvam-application-local-variance-backen-4bc87d65: safety suite unavailable
- 20260926T124721896487Z-sarvam-application-local-variance-backen-4bc87d65: RAG/agent suite unavailable
- 20260926T124721896487Z-sarvam-application-local-variance-backen-4bc87d65: cost per successful task unavailable
- 20260926T124734097204Z-sarvam-application-local-variance-backen-17676650: safety suite unavailable
- 20260926T124734097204Z-sarvam-application-local-variance-backen-17676650: RAG/agent suite unavailable
- 20260926T124734097204Z-sarvam-application-local-variance-backen-17676650: cost per successful task unavailable

## Limitations

- No causal conclusions are drawn from observed configuration differences.
- RCS is experimental and is not a standard universal metric.
- Human-review agreement measures consistency, not correctness or safety validity.

## Reproducibility

Underlying run IDs, config hashes, dataset hashes, prompt hashes, and artifact paths are preserved in `study_summary.json` and `comparison_table.csv`.
