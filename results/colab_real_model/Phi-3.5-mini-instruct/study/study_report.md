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
| `20260926T131715918748Z-sarvam-application-local-variance-baseli-dbed98ff` | `microsoft/Phi-3.5-mini-instruct` / `main` | `LOCAL_REAL_MODEL` | `179feac5e08eaf45` | 0.0000 | [0.0000, 0.0000] |
| `20260926T132047108421Z-sarvam-application-local-variance-backen-441d8119` | `microsoft/Phi-3.5-mini-instruct` / `main` | `LOCAL_REAL_MODEL` | `50e09e9b4d43b29b` | 0.0000 | [0.0000, 0.0000] |
| `20260926T132403236096Z-sarvam-application-local-variance-backen-2ca5fca7` | `microsoft/Phi-3.5-mini-instruct` / `main` | `LOCAL_REAL_MODEL` | `7c925b2129c67f24` | 0.0000 | [0.0000, 0.0000] |

## Comparisons

- `20260926T131715918748Z-sarvam-application-local-variance-baseli-dbed98ff` → `20260926T132047108421Z-sarvam-application-local-variance-backen-441d8119`: delta `0.0000`, 95% CI `[0.0000, 0.0000]`, effect `unavailable`, status **NO_MEANINGFUL_CHANGE**, practically meaningful: `False`.
- `20260926T131715918748Z-sarvam-application-local-variance-baseli-dbed98ff` → `20260926T132403236096Z-sarvam-application-local-variance-backen-2ca5fca7`: delta `0.0000`, 95% CI `[0.0000, 0.0000]`, effect `unavailable`, status **NO_MEANINGFUL_CHANGE**, practically meaningful: `False`.

## Experimental Robust Capability Score

- Mean quality: `0.0000`
- Configuration variance: `0.0000`
- Lambda: `1.0000`
- RCS: `0.0000`
- Experimental: `True`

## Safety, RAG/agent, and deployment

- `20260926T131715918748Z-sarvam-application-local-variance-baseli-dbed98ff`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `5688.2091`, cost/success `unavailable`, gate `INCONCLUSIVE`.
- `20260926T132047108421Z-sarvam-application-local-variance-backen-441d8119`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `5756.4049`, cost/success `unavailable`, gate `INCONCLUSIVE`.
- `20260926T132403236096Z-sarvam-application-local-variance-backen-2ca5fca7`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `5752.0515`, cost/success `unavailable`, gate `INCONCLUSIVE`.

## Pareto frontier

- Pareto-optimal: `0`
- Dominated: `0`
- Excluded/inconclusive: `3`

## Failure fingerprints

- `20260926T131715918748Z-sarvam-application-local-variance-baseli-dbed98ff`: failures `38`, rate `1.0000`, priority `P0`.
- `20260926T132047108421Z-sarvam-application-local-variance-backen-441d8119`: failures `38`, rate `1.0000`, priority `P0`.
- `20260926T132403236096Z-sarvam-application-local-variance-backen-2ca5fca7`: failures `38`, rate `1.0000`, priority `P0`.

## Human review

- Status: `NOT_PROVIDED`
- Human reviewed: `False`

## Missing evidence / inconclusive results

- 20260926T131715918748Z-sarvam-application-local-variance-baseli-dbed98ff: safety suite unavailable
- 20260926T131715918748Z-sarvam-application-local-variance-baseli-dbed98ff: RAG/agent suite unavailable
- 20260926T131715918748Z-sarvam-application-local-variance-baseli-dbed98ff: cost per successful task unavailable
- 20260926T132047108421Z-sarvam-application-local-variance-backen-441d8119: safety suite unavailable
- 20260926T132047108421Z-sarvam-application-local-variance-backen-441d8119: RAG/agent suite unavailable
- 20260926T132047108421Z-sarvam-application-local-variance-backen-441d8119: cost per successful task unavailable
- 20260926T132403236096Z-sarvam-application-local-variance-backen-2ca5fca7: safety suite unavailable
- 20260926T132403236096Z-sarvam-application-local-variance-backen-2ca5fca7: RAG/agent suite unavailable
- 20260926T132403236096Z-sarvam-application-local-variance-backen-2ca5fca7: cost per successful task unavailable

## Limitations

- No causal conclusions are drawn from observed configuration differences.
- RCS is experimental and is not a standard universal metric.
- Human-review agreement measures consistency, not correctness or safety validity.

## Reproducibility

Underlying run IDs, config hashes, dataset hashes, prompt hashes, and artifact paths are preserved in `study_summary.json` and `comparison_table.csv`.
