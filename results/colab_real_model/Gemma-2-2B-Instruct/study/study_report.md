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
| `20260926T182545096800Z-sarvam-application-local-variance-baseli-b685d607` | `google/gemma-2-2b-it` / `main` | `LOCAL_REAL_MODEL` | `ba20283c3ee4f28a` | 0.2105 | [0.1053, 0.3421] |
| `20260926T182752181561Z-sarvam-application-local-variance-backen-47df3806` | `google/gemma-2-2b-it` / `main` | `LOCAL_REAL_MODEL` | `43a58048a68e1d4b` | 0.2105 | [0.1053, 0.3421] |
| `20260926T182939461728Z-sarvam-application-local-variance-backen-80d3657e` | `google/gemma-2-2b-it` / `main` | `LOCAL_REAL_MODEL` | `878c1700d084b9f1` | 0.2105 | [0.1053, 0.3421] |

## Comparisons

- `20260926T182545096800Z-sarvam-application-local-variance-baseli-b685d607` → `20260926T182752181561Z-sarvam-application-local-variance-backen-47df3806`: delta `0.0000`, 95% CI `[0.0000, 0.0000]`, effect `unavailable`, status **NO_MEANINGFUL_CHANGE**, practically meaningful: `False`.
- `20260926T182545096800Z-sarvam-application-local-variance-baseli-b685d607` → `20260926T182939461728Z-sarvam-application-local-variance-backen-80d3657e`: delta `0.0000`, 95% CI `[0.0000, 0.0000]`, effect `unavailable`, status **NO_MEANINGFUL_CHANGE**, practically meaningful: `False`.

## Experimental Robust Capability Score

- Mean quality: `0.2105`
- Configuration variance: `0.0000`
- Lambda: `1.0000`
- RCS: `0.2105`
- Experimental: `True`

## Safety, RAG/agent, and deployment

- `20260926T182545096800Z-sarvam-application-local-variance-baseli-b685d607`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `8544.3569`, cost/success `unavailable`, gate `INCONCLUSIVE`.
- `20260926T182752181561Z-sarvam-application-local-variance-backen-47df3806`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `7784.5273`, cost/success `unavailable`, gate `INCONCLUSIVE`.
- `20260926T182939461728Z-sarvam-application-local-variance-backen-80d3657e`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `7868.7982`, cost/success `unavailable`, gate `INCONCLUSIVE`.

## Pareto frontier

- Pareto-optimal: `0`
- Dominated: `0`
- Excluded/inconclusive: `3`

## Failure fingerprints

- `20260926T182545096800Z-sarvam-application-local-variance-baseli-b685d607`: failures `30`, rate `0.7895`, priority `P0`.
- `20260926T182752181561Z-sarvam-application-local-variance-backen-47df3806`: failures `30`, rate `0.7895`, priority `P0`.
- `20260926T182939461728Z-sarvam-application-local-variance-backen-80d3657e`: failures `30`, rate `0.7895`, priority `P0`.

## Human review

- Status: `NOT_PROVIDED`
- Human reviewed: `False`

## Missing evidence / inconclusive results

- 20260926T182545096800Z-sarvam-application-local-variance-baseli-b685d607: safety suite unavailable
- 20260926T182545096800Z-sarvam-application-local-variance-baseli-b685d607: RAG/agent suite unavailable
- 20260926T182545096800Z-sarvam-application-local-variance-baseli-b685d607: cost per successful task unavailable
- 20260926T182752181561Z-sarvam-application-local-variance-backen-47df3806: safety suite unavailable
- 20260926T182752181561Z-sarvam-application-local-variance-backen-47df3806: RAG/agent suite unavailable
- 20260926T182752181561Z-sarvam-application-local-variance-backen-47df3806: cost per successful task unavailable
- 20260926T182939461728Z-sarvam-application-local-variance-backen-80d3657e: safety suite unavailable
- 20260926T182939461728Z-sarvam-application-local-variance-backen-80d3657e: RAG/agent suite unavailable
- 20260926T182939461728Z-sarvam-application-local-variance-backen-80d3657e: cost per successful task unavailable

## Limitations

- No causal conclusions are drawn from observed configuration differences.
- RCS is experimental and is not a standard universal metric.
- Human-review agreement measures consistency, not correctness or safety validity.

## Reproducibility

Underlying run IDs, config hashes, dataset hashes, prompt hashes, and artifact paths are preserved in `study_summary.json` and `comparison_table.csv`.
