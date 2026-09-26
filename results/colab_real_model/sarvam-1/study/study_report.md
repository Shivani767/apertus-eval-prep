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
| `20260926T132300829331Z-sarvam-application-local-variance-baseli-a399cf0a` | `sarvamai/sarvam-1` / `main` | `LOCAL_REAL_MODEL` | `aebdf6d5c3647914` | 0.0000 | [0.0000, 0.0000] |
| `20260926T132652652365Z-sarvam-application-local-variance-backen-c70801f7` | `sarvamai/sarvam-1` / `main` | `LOCAL_REAL_MODEL` | `477ee10df6b7fdfd` | 0.0000 | [0.0000, 0.0000] |
| `20260926T133031521337Z-sarvam-application-local-variance-backen-2a7a98ac` | `sarvamai/sarvam-1` / `main` | `LOCAL_REAL_MODEL` | `01d01feb572c842f` | 0.0000 | [0.0000, 0.0000] |

## Comparisons

- `20260926T132300829331Z-sarvam-application-local-variance-baseli-a399cf0a` → `20260926T132652652365Z-sarvam-application-local-variance-backen-c70801f7`: delta `0.0000`, 95% CI `[0.0000, 0.0000]`, effect `unavailable`, status **NO_MEANINGFUL_CHANGE**, practically meaningful: `False`.
- `20260926T132300829331Z-sarvam-application-local-variance-baseli-a399cf0a` → `20260926T133031521337Z-sarvam-application-local-variance-backen-2a7a98ac`: delta `0.0000`, 95% CI `[0.0000, 0.0000]`, effect `unavailable`, status **NO_MEANINGFUL_CHANGE**, practically meaningful: `False`.

## Experimental Robust Capability Score

- Mean quality: `0.0000`
- Configuration variance: `0.0000`
- Lambda: `1.0000`
- RCS: `0.0000`
- Experimental: `True`

## Safety, RAG/agent, and deployment

- `20260926T132300829331Z-sarvam-application-local-variance-baseli-a399cf0a`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `5892.4628`, cost/success `unavailable`, gate `INCONCLUSIVE`.
- `20260926T132652652365Z-sarvam-application-local-variance-backen-c70801f7`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `5825.9671`, cost/success `unavailable`, gate `INCONCLUSIVE`.
- `20260926T133031521337Z-sarvam-application-local-variance-backen-2a7a98ac`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `5835.2646`, cost/success `unavailable`, gate `INCONCLUSIVE`.

## Pareto frontier

- Pareto-optimal: `0`
- Dominated: `0`
- Excluded/inconclusive: `3`

## Failure fingerprints

- `20260926T132300829331Z-sarvam-application-local-variance-baseli-a399cf0a`: failures `38`, rate `1.0000`, priority `P0`.
- `20260926T132652652365Z-sarvam-application-local-variance-backen-c70801f7`: failures `38`, rate `1.0000`, priority `P0`.
- `20260926T133031521337Z-sarvam-application-local-variance-backen-2a7a98ac`: failures `38`, rate `1.0000`, priority `P0`.

## Human review

- Status: `NOT_PROVIDED`
- Human reviewed: `False`

## Missing evidence / inconclusive results

- 20260926T132300829331Z-sarvam-application-local-variance-baseli-a399cf0a: safety suite unavailable
- 20260926T132300829331Z-sarvam-application-local-variance-baseli-a399cf0a: RAG/agent suite unavailable
- 20260926T132300829331Z-sarvam-application-local-variance-baseli-a399cf0a: cost per successful task unavailable
- 20260926T132652652365Z-sarvam-application-local-variance-backen-c70801f7: safety suite unavailable
- 20260926T132652652365Z-sarvam-application-local-variance-backen-c70801f7: RAG/agent suite unavailable
- 20260926T132652652365Z-sarvam-application-local-variance-backen-c70801f7: cost per successful task unavailable
- 20260926T133031521337Z-sarvam-application-local-variance-backen-2a7a98ac: safety suite unavailable
- 20260926T133031521337Z-sarvam-application-local-variance-backen-2a7a98ac: RAG/agent suite unavailable
- 20260926T133031521337Z-sarvam-application-local-variance-backen-2a7a98ac: cost per successful task unavailable

## Limitations

- No causal conclusions are drawn from observed configuration differences.
- RCS is experimental and is not a standard universal metric.
- Human-review agreement measures consistency, not correctness or safety validity.

## Reproducibility

Underlying run IDs, config hashes, dataset hashes, prompt hashes, and artifact paths are preserved in `study_summary.json` and `comparison_table.csv`.
