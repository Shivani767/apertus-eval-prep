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
| `20260926T125457034355Z-sarvam-application-local-variance-baseli-5dc7dbf3` | `Qwen/Qwen2.5-1.5B-Instruct` / `main` | `LOCAL_REAL_MODEL` | `e0ab5774b7801c6d` | 0.0789 | [0.0000, 0.1579] |
| `20260926T125723102727Z-sarvam-application-local-variance-backen-16a89773` | `Qwen/Qwen2.5-1.5B-Instruct` / `main` | `LOCAL_REAL_MODEL` | `14a4c6233790852e` | 0.0789 | [0.0000, 0.1579] |
| `20260926T130002884423Z-sarvam-application-local-variance-backen-d5344af7` | `Qwen/Qwen2.5-1.5B-Instruct` / `main` | `LOCAL_REAL_MODEL` | `3f2081908c89567d` | 0.0789 | [0.0000, 0.1579] |

## Comparisons

- `20260926T125457034355Z-sarvam-application-local-variance-baseli-5dc7dbf3` → `20260926T125723102727Z-sarvam-application-local-variance-backen-16a89773`: delta `0.0000`, 95% CI `[0.0000, 0.0000]`, effect `unavailable`, status **NO_MEANINGFUL_CHANGE**, practically meaningful: `False`.
- `20260926T125457034355Z-sarvam-application-local-variance-baseli-5dc7dbf3` → `20260926T130002884423Z-sarvam-application-local-variance-backen-d5344af7`: delta `0.0000`, 95% CI `[0.0000, 0.0000]`, effect `unavailable`, status **NO_MEANINGFUL_CHANGE**, practically meaningful: `False`.

## Experimental Robust Capability Score

- Mean quality: `0.0789`
- Configuration variance: `0.0000`
- Lambda: `1.0000`
- RCS: `0.0789`
- Experimental: `True`

## Safety, RAG/agent, and deployment

- `20260926T125457034355Z-sarvam-application-local-variance-baseli-5dc7dbf3`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `5990.6514`, cost/success `unavailable`, gate `INCONCLUSIVE`.
- `20260926T125723102727Z-sarvam-application-local-variance-backen-16a89773`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `9721.1049`, cost/success `unavailable`, gate `INCONCLUSIVE`.
- `20260926T130002884423Z-sarvam-application-local-variance-backen-d5344af7`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `6152.0363`, cost/success `unavailable`, gate `INCONCLUSIVE`.

## Pareto frontier

- Pareto-optimal: `0`
- Dominated: `0`
- Excluded/inconclusive: `3`

## Failure fingerprints

- `20260926T125457034355Z-sarvam-application-local-variance-baseli-5dc7dbf3`: failures `35`, rate `0.9211`, priority `P0`.
- `20260926T125723102727Z-sarvam-application-local-variance-backen-16a89773`: failures `35`, rate `0.9211`, priority `P0`.
- `20260926T130002884423Z-sarvam-application-local-variance-backen-d5344af7`: failures `35`, rate `0.9211`, priority `P0`.

## Human review

- Status: `NOT_PROVIDED`
- Human reviewed: `False`

## Missing evidence / inconclusive results

- 20260926T125457034355Z-sarvam-application-local-variance-baseli-5dc7dbf3: safety suite unavailable
- 20260926T125457034355Z-sarvam-application-local-variance-baseli-5dc7dbf3: RAG/agent suite unavailable
- 20260926T125457034355Z-sarvam-application-local-variance-baseli-5dc7dbf3: cost per successful task unavailable
- 20260926T125723102727Z-sarvam-application-local-variance-backen-16a89773: safety suite unavailable
- 20260926T125723102727Z-sarvam-application-local-variance-backen-16a89773: RAG/agent suite unavailable
- 20260926T125723102727Z-sarvam-application-local-variance-backen-16a89773: cost per successful task unavailable
- 20260926T130002884423Z-sarvam-application-local-variance-backen-d5344af7: safety suite unavailable
- 20260926T130002884423Z-sarvam-application-local-variance-backen-d5344af7: RAG/agent suite unavailable
- 20260926T130002884423Z-sarvam-application-local-variance-backen-d5344af7: cost per successful task unavailable

## Limitations

- No causal conclusions are drawn from observed configuration differences.
- RCS is experimental and is not a standard universal metric.
- Human-review agreement measures consistency, not correctness or safety validity.

## Reproducibility

Underlying run IDs, config hashes, dataset hashes, prompt hashes, and artifact paths are preserved in `study_summary.json` and `comparison_table.csv`.
