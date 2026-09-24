# Research status — supersedes all previous readiness assessments

**Overall: NEEDS EXPERIMENTS / NEEDS REVISION. Not submission-ready.** No model inference was performed during this reanalysis.

1. **Title:** Configuration Sensitivity in LLM Evaluation: An Artifact-Based Case Study.
2. **Research question:** How do stored extracted-answer scores and rankings vary across observed configurations on frozen slices?
3. **Hypothesis:** Configuration-conditional measurement is a useful framing here, not a universal theorem.
4. **Actual scope:** 31 successful runs × 800 frozen IDs = 24,800 repeated output records, not independent questions. Nominal OFAT labels; effective environments are not verified as matched.
5. **Models:** Four total; three in the shared matrix plus one Qwen2.5-7B INT4 cell. No Apertus-model inference in the selected registry.
6. **Benchmarks:** Four 200-item slices: ARC-Easy, GSM8K, HellaSwag, MGSM EN/DE/FR. Not full benchmark or leaderboard protocols.
7. **Configurations:** Eight shared greedy settings; eleven nominal settings including sampled seeds; 27 non-control same-model contrasts. Settings are not model/config cells.
8. **Seeds:** 0, 1, 2; greedy for three models, sampled for two. Greedy repeats are not independent stochastic evidence.
9. **Findings:** Qwen prompt range (549−410)/800 = 17.375 pp; control Phi-minus-Qwen (536−515)/800 = 2.625 pp; five-shot Qwen-minus-Phi (549−451)/800 = 12.250 pp. Only five-shot changes shared point-estimate ordering. Concise favors Phi and five-shot favors Qwen in exploratory conditional paired tests. Non-significance is not equivalence.
10. **Strongest figure:** `figures/prompt_forest.pdf`.
11. **Strongest table:** `tables/audited_head_to_head.tex`: paired differences, pointwise bootstrap intervals, exact McNemar/Holm.
12. **Contribution:** Audited case study and reproducible analysis. Novel/first evaluation principle, isolated causal effects, validated ERS and interaction effects: **NOT SUPPORTED**.
13. **Limitations:** Unpinned revisions, software drift, missing effective prompts/precision/defaults, permissive extractor, selected small models/tasks/configs, related questions, no independent confirmation, missing Phi sampling, unvalidated efficiency comparison.
14. **Missing before stronger submission:** Blinded output adjudication and prespecified parser comparisons; matched-environment headline reruns with immutable revisions and full effective settings; semantic question clusters for dependence-aware inference. Complete Phi sampling before sampled-ranking claims. Factorial/broader studies are needed for broader claims. Finish metadata, author, license and visual review.
15. **Reproducibility:** **READY** for stored-output analysis: raw rescoring, source SHA-256 ledger, exact-count statistics and deterministic asset checks pass. Exact historical inference: **NOT SUPPORTED**. Changes have not been committed automatically.
16. **LaTeX:** **READY** for tested clean-source Tectonic build: `make paper` returned exit 0 and regenerated a 10-page total PDF. Final log has no overflow, missing characters, unresolved references or duplicate labels. Cached packages were used; PDFLaTeX and arXiv servers were not tested. Page-by-page visual inspection: **NEEDS REVISION**. Content was not padded to a page target.
17. **arXiv readiness:** **NEEDS EXPERIMENTS / NEEDS REVISION**. Proposed cs.LG; optional cs.CL is justified. No cs.AI cross-list needed. Draft not submitted, accepted, published or peer reviewed.

## Follow-up infrastructure

A metadata-blinded answer-review exporter and pilot annotation protocol are available. The actual local pilot contains 320 **UNREVIEWED** records; its two unit tests passed. Exporting these records does not complete adjudication or validate extraction. See [FOLLOWUP_STATUS.md](FOLLOWUP_STATUS.md) and [ANSWER_REVIEW_PROTOCOL.md](ANSWER_REVIEW_PROTOCOL.md) for scope, observed checks and remaining blockers.

## Verified checkpoint

262 tests passed, including manuscript-specific, review-export and strict-parser regressions. Six numerical tables plus headline macros and five vector plots regenerate from raw outputs. The latest validator passed with 13 active TeX inputs and 13 citations. Regenerating the canonical audited analysis changed only its source-hash ledger; statistical values and paper tables were identical. Only active dependencies enter the source bundle. Legacy manuscript sections/tables are superseded and excluded; see README.md. Technical checks do not certify scientific validity.

The opt-in strict math-parser comparison completed on 12,400 repeated outputs and is archived separately in `analysis/parser_sensitivity.json`. It is a **post-hoc format-sensitivity diagnostic, not held-out validation**; historical scores are unchanged. See [PARSER_SENSITIVITY_STATUS.md](PARSER_SENSITIVITY_STATUS.md) for exact counts, provenance checks, interpretation and reproduction instructions. Independent adjudication and matched-environment confirmation remain submission blockers.

