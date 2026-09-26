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
| `20260926T132428028217Z-sarvam-application-local-variance-baseli-564f6c9c` | `HuggingFaceTB/SmolLM3-3B` / `main` | `LOCAL_REAL_MODEL` | `856a571f149b56ca` | 0.0000 | [0.0000, 0.0000] |
| `20260926T132906748101Z-sarvam-application-local-variance-backen-115ad69e` | `HuggingFaceTB/SmolLM3-3B` / `main` | `LOCAL_REAL_MODEL` | `12ca4d1d81105f21` | 0.0000 | [0.0000, 0.0000] |
| `20260926T133335216948Z-sarvam-application-local-variance-backen-68376bcf` | `HuggingFaceTB/SmolLM3-3B` / `main` | `LOCAL_REAL_MODEL` | `39a5930d6fe14a58` | 0.0000 | [0.0000, 0.0000] |

## Comparisons

- `20260926T132428028217Z-sarvam-application-local-variance-baseli-564f6c9c` → `20260926T132906748101Z-sarvam-application-local-variance-backen-115ad69e`: delta `0.0000`, 95% CI `[0.0000, 0.0000]`, effect `unavailable`, status **NO_MEANINGFUL_CHANGE**, practically meaningful: `False`.
- `20260926T132428028217Z-sarvam-application-local-variance-baseli-564f6c9c` → `20260926T133335216948Z-sarvam-application-local-variance-backen-68376bcf`: delta `0.0000`, 95% CI `[0.0000, 0.0000]`, effect `unavailable`, status **NO_MEANINGFUL_CHANGE**, practically meaningful: `False`.

## Experimental Robust Capability Score

- Mean quality: `0.0000`
- Configuration variance: `0.0000`
- Lambda: `1.0000`
- RCS: `0.0000`
- Experimental: `True`

## Safety, RAG/agent, and deployment

- `20260926T132428028217Z-sarvam-application-local-variance-baseli-564f6c9c`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `7235.4223`, cost/success `unavailable`, gate `INCONCLUSIVE`.
- `20260926T132906748101Z-sarvam-application-local-variance-backen-115ad69e`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `7254.5395`, cost/success `unavailable`, gate `INCONCLUSIVE`.
- `20260926T133335216948Z-sarvam-application-local-variance-backen-68376bcf`: attack success `unavailable`, groundedness `unavailable`, agent success `unavailable`, latency p95 `7211.0256`, cost/success `unavailable`, gate `INCONCLUSIVE`.

## Pareto frontier

- Pareto-optimal: `0`
- Dominated: `0`
- Excluded/inconclusive: `3`

## Failure fingerprints

- `20260926T132428028217Z-sarvam-application-local-variance-baseli-564f6c9c`: failures `38`, rate `1.0000`, priority `P0`.
- `20260926T132906748101Z-sarvam-application-local-variance-backen-115ad69e`: failures `38`, rate `1.0000`, priority `P0`.
- `20260926T133335216948Z-sarvam-application-local-variance-backen-68376bcf`: failures `38`, rate `1.0000`, priority `P0`.

## Human review

- Status: `NOT_PROVIDED`
- Human reviewed: `False`

## Missing evidence / inconclusive results

- 20260926T132428028217Z-sarvam-application-local-variance-baseli-564f6c9c: safety suite unavailable
- 20260926T132428028217Z-sarvam-application-local-variance-baseli-564f6c9c: RAG/agent suite unavailable
- 20260926T132428028217Z-sarvam-application-local-variance-baseli-564f6c9c: cost per successful task unavailable
- 20260926T132906748101Z-sarvam-application-local-variance-backen-115ad69e: safety suite unavailable
- 20260926T132906748101Z-sarvam-application-local-variance-backen-115ad69e: RAG/agent suite unavailable
- 20260926T132906748101Z-sarvam-application-local-variance-backen-115ad69e: cost per successful task unavailable
- 20260926T133335216948Z-sarvam-application-local-variance-backen-68376bcf: safety suite unavailable
- 20260926T133335216948Z-sarvam-application-local-variance-backen-68376bcf: RAG/agent suite unavailable
- 20260926T133335216948Z-sarvam-application-local-variance-backen-68376bcf: cost per successful task unavailable

## Limitations

- No causal conclusions are drawn from observed configuration differences.
- RCS is experimental and is not a standard universal metric.
- Human-review agreement measures consistency, not correctness or safety validity.

## Reproducibility

Underlying run IDs, config hashes, dataset hashes, prompt hashes, and artifact paths are preserved in `study_summary.json` and `comparison_table.csv`.
