# Repository evidence audit — 2026-09-16

This is a working-tree audit, not independent authentication of historical inference. `analysis/repository_inventory.json` fingerprints source, tests, configurations, data, documentation, notebooks, dashboard, reports and parent archives. Dependencies, Git internals and compiled frontend bundles are excluded. Detailed source review concentrates on the inference-to-score-to-paper path. Existing reports and notebook outputs are not independent experiments.

## A–V inventory

| Field | Evidence |
|---|---|
| A. Models | Paper: SmolLM2-1.7B-Instruct, Qwen2.5-3B-Instruct, Phi-3.5-mini-instruct, plus one Qwen2.5-7B-Instruct INT4 run. Qwen2.5-0.5B-Instruct smoke/canary runs excluded. No Apertus-model inference evidenced. |
| B. Revisions | All paper manifests: revision=null. Version not recorded in the current artifact. Resolved tokenizer revisions/templates absent. |
| C–D. Benchmarks | 200 local rows each: ARC-Easy test, GSM8K test, HellaSwag validation, MGSM test EN/DE/FR. IDs/revisions in data/official/SOURCES.md and snapshot_benchmarks.py. Not full benchmark/leaderboard scores. |
| E–G. Prompts | configs/prompts/{default,concise,5shot}.yaml. Default math requests reasoning; concise prohibits other text. Five-shot prepends task-specific answer-only exemplars. Tokenizer template selected but rendered bytes not archived. |
| H–J. Inference | HF generate, vLLM completion; HF bitsandbytes INT8/NF4. dtype=auto, not effective dtype, recorded. Current CUDA HF requests BF16 without quantization and FP16 with quantization; vLLM resolves auto separately. Thus these are implementation bundles. Greedy T=0/top-p=1; sampled T=0.7/top-p=0.95; max_new_tokens=256, batch_size=1. Remaining backend defaults not fully recorded. |
| K–M. Runtime | Seeds 0/1/2; Tesla T4; Python 3.12.13/3.13.15; torch 2.11.0+cu128; Transformers 5.15.0/5.15.1/5.16.1; installed vLLM 0.26.0 or 0.24.0+cu129; harness 0.2.0/0.4.0. Recorded strings, not independently authenticated environments. bitsandbytes/driver/complete lock absent. |
| N–O. Counts | 31 completed runs × 800 distinct IDs = 24,800 output records, not independent questions. Eight shared greedy configurations × three models, six sampled cells × two models, one 7B cell. Eleven nominal configurations including sampled seeds. Planned T4 matrix 34 cells; Phi sampling missing. |
| P–Q. Metrics | Extracted-answer accuracy, Wilson intervals, McNemar/Holm/BH, Kendall tau-b, configuration bootstrap, win fractions, provisional ERS. Existing paper arithmetic subtracts rounded accuracies and rounds p before adjustment; repair required. Wilson overlap is not equivalence. |
| R. Results | Controls Smol 318/800, Qwen 515/800, Phi 536/800. Qwen concise 410/800, five-shot 549/800; Phi five-shot 451/800. Prompt range 139/800=17.375 pp; control gap 21/800=2.625 pp; five-shot Qwen-Phi gap 98/800=12.25 pp. |
| S. Limitations | Unpinned weights, software drift, missing source objects, unknown effective templates/precision, selected small models/tasks/configurations, translated/dependent questions, permissive extractor, no confirmation run. |
| T. Reproduction | All 31 runs match frozen IDs/golds and current rescoring with zero mismatches. This validates arithmetic, not semantic extraction/historical execution. Four of 14 recorded Git objects absent locally. Settings hash excludes source/package/data bytes and system prompt: not a complete experiment hash. |
| U. Assets | Five PDF plots, eleven generated tables; some main tables not included. Tectonic available; BibTeX truncation, duplicate labels and overflow found. |
| V. Unsupported claims | Full provenance, verified identical backend prompts, isolated causal OFAT effects, CI-overlap statistical ties, output determinism from correctness equality, validated ERS, no missing experiments, fully verified metadata. |

## Selection and design

Parent ZIPs contain differing historical copies: do not merge or count checkpoints as runs. The paper registry is the explicit evidence boundary; other run metadata is in the inventory. Synthetic replay/factorial fixtures are software tests only. The nested prompt × runtime × seed plan exists; no completed real factorial design appears in the paper registry. Greedy seeds are not stochastic replicates.

Dashboard exports use separate CI/ranking conventions and a selected chart subset; they are not the paper's numerical authority. Historical docs contain stale test counts, a future-dated audit and an incorrect assertion that the repository contains no answer keys. Those assertions are not adopted.

## Retained questions

How much do observed extracted-answer scores vary? Does point-estimate ordering change in the complete matrix? How do score ranges compare with model gaps? These are descriptive conditional questions. General causal dimension importance, calibrated ERS and factorial interaction inference are NOT SUPPORTED. Contribution: an auditable small empirical case study and reproducible analysis, not a new evaluation principle.

## Submission gates

Adjudicate extractor behavior; confirm headline contrasts with pinned model/tokenizer revisions and matched environments; archive effective prompts, precision, generation defaults, source and failures. Finish citation/author/license reviews. Broader claims require factorial/larger-model measurements, not synthetic substitutes.
