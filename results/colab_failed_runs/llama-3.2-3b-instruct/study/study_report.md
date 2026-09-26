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
| `20260926T180416184193Z-sarvam-application-local-variance-baseli-6c3b5837` | `meta-llama/Llama-3.2-3B-Instruct` / `0cb88a4f764b7a12671c53f0838cd831a0843b95` | `LOCAL_REAL_MODEL` | `9f25f6052ab41a4a` | unavailable | [unavailable, unavailable] |
| `20260926T180428729455Z-sarvam-application-local-variance-backen-f5331ed7` | `meta-llama/Llama-3.2-3B-Instruct` / `0cb88a4f764b7a12671c53f0838cd831a0843b95` | `LOCAL_REAL_MODEL` | `4adbe32ae75e7e00` | unavailable | [unavailable, unavailable] |
| `20260926T180434961387Z-sarvam-application-local-variance-backen-2a9b253e` | `meta-llama/Llama-3.2-3B-Instruct` / `0cb88a4f764b7a12671c53f0838cd831a0843b95` | `LOCAL_REAL_MODEL` | `7ee9f121280ce0ad` | unavailable | [unavailable, unavailable] |

## Comparisons

- `20260926T180416184193Z-sarvam-application-local-variance-baseli-6c3b5837` → `20260926T180428729455Z-sarvam-application-local-variance-backen-f5331ed7`: delta `unavailable`, 95% CI `[unavailable, unavailable]`, effect `unavailable`, status **INCONCLUSIVE**, practically meaningful: `False`.
- `20260926T180416184193Z-sarvam-application-local-variance-baseli-6c3b5837` → `20260926T180434961387Z-sarvam-application-local-variance-backen-2a9b253e`: delta `unavailable`, 95% CI `[unavailable, unavailable]`, effect `unavailable`, status **INCONCLUSIVE**, practically meaningful: `False`.

## Experimental Robust Capability Score

- Mean quality: `unavailable`
- Configuration variance: `unavailable`
- Lambda: `1.0000`
- RCS: `unavailable`
- Experimental: `True`

## Safety, RAG/agent, and deployment

- `20260926T180416184193Z-sarvam-application-local-variance-baseli-6c3b5837`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `unavailable`, cost/success `unavailable`, gate `INCONCLUSIVE`.
- `20260926T180428729455Z-sarvam-application-local-variance-backen-f5331ed7`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `unavailable`, cost/success `unavailable`, gate `INCONCLUSIVE`.
- `20260926T180434961387Z-sarvam-application-local-variance-backen-2a9b253e`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `unavailable`, cost/success `unavailable`, gate `INCONCLUSIVE`.

## Pareto frontier

- Pareto-optimal: `0`
- Dominated: `0`
- Excluded/inconclusive: `3`

## Failure fingerprints

- `20260926T180416184193Z-sarvam-application-local-variance-baseli-6c3b5837`: failures `38`, rate `1.0000`, priority `P0`.
- `20260926T180428729455Z-sarvam-application-local-variance-backen-f5331ed7`: failures `38`, rate `1.0000`, priority `P0`.
- `20260926T180434961387Z-sarvam-application-local-variance-backen-2a9b253e`: failures `38`, rate `1.0000`, priority `P0`.

## Human review

- Status: `NOT_PROVIDED`
- Human reviewed: `False`

## Missing evidence / inconclusive results

- 20260926T180416184193Z-sarvam-application-local-variance-baseli-6c3b5837: safety suite unavailable
- 20260926T180416184193Z-sarvam-application-local-variance-baseli-6c3b5837: RAG/agent suite unavailable
- 20260926T180416184193Z-sarvam-application-local-variance-baseli-6c3b5837: cost per successful task unavailable
- 20260926T180428729455Z-sarvam-application-local-variance-backen-f5331ed7: safety suite unavailable
- 20260926T180428729455Z-sarvam-application-local-variance-backen-f5331ed7: RAG/agent suite unavailable
- 20260926T180428729455Z-sarvam-application-local-variance-backen-f5331ed7: cost per successful task unavailable
- 20260926T180434961387Z-sarvam-application-local-variance-backen-2a9b253e: safety suite unavailable
- 20260926T180434961387Z-sarvam-application-local-variance-backen-2a9b253e: RAG/agent suite unavailable
- 20260926T180434961387Z-sarvam-application-local-variance-backen-2a9b253e: cost per successful task unavailable

## Limitations

- No causal conclusions are drawn from observed configuration differences.
- RCS is experimental and is not a standard universal metric.
- Human-review agreement measures consistency, not correctness or safety validity.

## Reproducibility

Underlying run IDs, config hashes, dataset hashes, prompt hashes, and artifact paths are preserved in `study_summary.json` and `comparison_table.csv`.
