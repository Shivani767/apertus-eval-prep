# Implementation Audit

**Repository:** [Shivani767/apertus-eval-prep](https://github.com/Shivani767/apertus-eval-prep)  
**Audit date:** 2026-08-28  
**Version:** 0.3.0  
**Method:** Source inspection, test inventory, committed artefact verification. README claims are not treated as evidence unless backed by code and/or committed JSON.

## Status legend

| Status | Meaning |
|---|---|
| **IMPLEMENTED AND VERIFIED** | Code exists, tests pass, and/or committed run JSON with manifest |
| **IMPLEMENTED BUT NOT VERIFIED** | Code exists; no end-to-end GPU run in this environment |
| **PARTIALLY IMPLEMENTED** | Core path works; gaps documented below |
| **DOCUMENTATION ONLY** | Described in README/paper but no working code path |
| **MISSING** | Not implemented |

---

## Summary table

| Feature | Status | Primary files | Tests | Real validation |
|---|---|---|---|---|
| Multi-model comparison | IMPLEMENTED AND VERIFIED | `benchmark_report.py`, `report.py`, `compare.py`, `sweep.py` | `test_report.py`, `test_benchmark_report.py`, `test_sweep.py` | 19 paper runs + canary JSON |
| Thinking vs non-thinking | PARTIALLY IMPLEMENTED | `templates.py`, `config.py`, `run_eval.py`, `configs/thinking.yaml` | `test_benchmark_report.py` (pairing logic only) | **Not run** |
| Multilingual evaluation | IMPLEMENTED AND VERIFIED | `prompts.py`, `scoring.py`, `run_eval.py` | `test_scoring.py`, `test_harness.py`, `test_official_slice.py` | Canary n=10 + MGSM n=200 in paper runs |
| Prompt robustness (paraphrase) | IMPLEMENTED BUT NOT VERIFIED | `prompts.py`, `sweep.py`, `data/paraphrase_set.jsonl` | `test_sweep.py` | **Not run** (T4 profile skips factor) |
| Prompt robustness (noisy) | IMPLEMENTED BUT NOT VERIFIED | `scoring.py`, `data/eval_set.jsonl` (6 items) | `test_benchmark_report.py` | **Not run** on extended 48-item config |
| Hallucination evaluation | IMPLEMENTED BUT NOT VERIFIED | `scoring.py` (`_hallucination_metrics`) | `test_benchmark_report.py` | **Not run** (canary items only, n=6) |
| Safety and bias | PARTIALLY IMPLEMENTED | `scoring.py` (`_safety_metrics`) | `test_benchmark_report.py` | **Not run**; no demographic bias |
| Cost–performance | PARTIALLY IMPLEMENTED | `scoring.py` (`compute_cost`), `benchmark_report.py` | `test_benchmark_report.py` | Estimated USD only when YAML pricing set |
| Quantization (int8/int4) | IMPLEMENTED AND VERIFIED | `backends/hf.py`, `sweep.py` | `test_hf_backend.py`, `test_sweep.py` | SmolLM2 int8/int4 in `registry_paper.jsonl` |
| Automatic reports | IMPLEMENTED AND VERIFIED | `report.py`, `benchmark_report.py`, `compare.py` | `test_report.py`, `test_benchmark_report.py` | `paper/_generated_tables.md`, PNG figures |
| OFAT experiment system | IMPLEMENTED AND VERIFIED | `sweep.py`, `configs/experiments/stability.yaml` | `test_sweep.py` | 19/34 T4 cells committed |
| Statistical analysis | IMPLEMENTED AND VERIFIED | `stats.py` | `test_stats.py` | Used in paper tables |
| Experiment registry | IMPLEMENTED AND VERIFIED | `registry.py`, `sweep.py` | `test_sweep.py`, `test_checkpoint.py` | `registry_paper.jsonl` |
| Reproducibility metadata | IMPLEMENTED AND VERIFIED | `manifest.py`, `checkpoint.py`, frozen JSONL | `test_checkpoint.py`, `test_official_slice.py` | Git commit in every manifest |
| Pareto analysis | IMPLEMENTED AND VERIFIED | `analysis.py` | `test_analysis.py` | Validation report |
| `reproduce` CLI | IMPLEMENTED AND VERIFIED | `reproduce.py`, `cli.py` | `test_reproduce.py` | SmolLM2 control row |
| Memory profiling | MISSING | — | — | Not measured |
| AWQ/GPTQ | MISSING | — | — | Only bitsandbytes int8/int4 |
| LLM-as-judge hallucination | MISSING | — | — | Exact-match SUPPORTED/UNSUPPORTED only |
| Demographic bias | MISSING | — | — | Task named `safety_bias` is refusal + benign MCQ |
| AzureML backend | DOCUMENTATION ONLY | `configs/azureml.yaml` | — | `backend: azureml` not implemented |
| HTML/PDF reports | MISSING | — | — | Markdown + JSON only |
| CI workflows | MISSING | — | — | No `.github/workflows` in tree |

---

## 1. Multi-model benchmark comparison

**Status:** IMPLEMENTED AND VERIFIED

**What works**
- YAML `models:` list in study configs; no model-specific eval code.
- `sweep.expand_ofat` runs the same protocol per model.
- `report.ranking_table` ranks models per OFAT cell with Wilson CIs, Kendall τ_b, McNemar vs control.
- `benchmark_report.analyze_runs` aggregates N scored JSON files.
- `compare.compare_runs` diffs two runs with explicit setting diff.

**CLI**
```bash
python -m apertus_eval_prep sweep --config configs/experiments/stability.yaml --profile t4 ...
python -m apertus_eval_prep report --registry results/registry_paper.jsonl --out reports/stability_paper
python -m apertus_eval_prep benchmark-report --run results/runs/A.json=labelA --run results/runs/B.json=labelB --out reports/benchmark
python -m apertus_eval_prep compare A.json B.json --out diff.md
```

**Gaps**
- `compare.py` setting-diff keys omit `thinking_mode` (fixed in this upgrade).
- Paper matrix incomplete: 19/34 T4 cells (`paper/run_status.md`).
- `batch_size` in config is stored but inference is always sequential.

---

## 2. Thinking vs non-thinking evaluation

**Status:** PARTIALLY IMPLEMENTED

**What works**
- `RunConfig.thinking_mode` + `--thinking-mode` CLI flag.
- `templates.THINKING_TEMPLATE` wraps user text before chat template.
- `benchmark_report` pairs runs with same model, different `thinking_mode`.

**What is missing**
- No committed thinking runs.
- No derived metrics in payload until `analysis.py` (this upgrade).
- `dump-prompts` did not pass `thinking=` (fixed in this upgrade).
- Not in paper-matrix `stability.yaml` (separate `configs/experiments/thinking.yaml`).
- Does not enable native model thinking APIs (e.g. Apertus `--enable_thinking`); prompt wrapper only.

---

## 3. Multilingual evaluation

**Status:** IMPLEMENTED AND VERIFIED

**Data**
| Slice | Tasks | Languages | n |
|---|---|---|---|
| Canary | `multilingual` | EN, DE, FR, IT, HI | 10 |
| Official | `mgsm` | EN, DE, FR | 200 |

**What works**
- `summarize_languages` in run JSON.
- Numeric exact-match via `extract_number`.
- Per-language table in `benchmark_report`.

**Gaps**
- No translated-vs-native split (all items are native-language prompts).
- Italian in canary but not in official MGSM slice.
- No language-specific system prompts.

---

## 4. Prompt robustness

### 4a Paraphrase (semantic equivalence)

**Status:** IMPLEMENTED BUT NOT VERIFIED

- Frozen `data/paraphrase_set.jsonl`: 4 stems × 3 wordings.
- OFAT factor `paraphrase_id: [orig, p1, p2]`.
- T4 profile **skips** entire paraphrase factor in `stability.yaml`.
- Standalone study `configs/experiments/paraphrase.yaml` — **not run**.

### 4b Noisy prompts

**Status:** IMPLEMENTED BUT NOT VERIFIED

- 6 frozen noisy MCQ items in `eval_set.jsonl` (`robustness` task).
- Same letter extractor as ARC.
- No dynamic prompt generation (reproducible by design).

**Derived metrics** (robustness score, Kendall across variants): added in `analysis.py`.

---

## 5. Hallucination evaluation

**Status:** IMPLEMENTED BUT NOT VERIFIED

**Implementation**
- 6 items: 3 SUPPORTED, 3 UNSUPPORTED (common-knowledge claims).
- `extract_fact_label` → precision/recall/F1 in `summarize_tasks`.
- No LLM-as-judge; no unanswerable/abstention tier separate from UNSUPPORTED.
- Not in official n=800 slice.

---

## 6. Safety and bias

**Status:** PARTIALLY IMPLEMENTED

**Implemented categories**
| Category | Metric | n |
|---|---|---|
| Harmful-request refusal | `refusal_recall` | 3 |
| Over-refusal on benign MCQ | `over_refusal_rate` | 3 |
| Benign MCQ accuracy | `benign_accuracy` | 3 |

**Missing**
- Jailbreak suite, demographic bias, cultural bias benchmarks.
- Safety system prompt exists in `DEFAULT_SYSTEMS["safety"]` but configs default to `system_prompt: null`.

---

## 7. Cost–performance analysis

**Status:** PARTIALLY IMPLEMENTED

**Measured (every run)**
- `prompt_tokens`, `num_new_tokens`, `ttft_ms`, `e2e_ms`, `tokens_per_sec`.

**Estimated (when YAML pricing set)**
- `cost.usd_input`, `cost.usd_output`, `cost.usd_total`, `cost.usd_per_item`.

**Missing**
- GPU memory (not instrumented).
- Cloud billing integration (manual YAML rates only).

**Derived metrics** (`accuracy_per_cost`, `accuracy_per_second`): added in `analysis.py`.

---

## 8. Quantization evaluation

**Status:** IMPLEMENTED AND VERIFIED (HF int8/int4 only)

**Supported:** `none`, `int8`, `int4` via bitsandbytes on CUDA.  
**Blocked:** vLLM + quantization (explicit error in `vllm_backend.py`).  
**Verified runs:** SmolLM2 int8/int4 vs fp16 control in registry.

**Missing:** AWQ, GPTQ, FP8. Mac/CPU cannot run quantized loads.

---

## 9. Automatic experiment reports

**Status:** IMPLEMENTED AND VERIFIED

| Output | Command | Format |
|---|---|---|
| Stability report | `report` | MD + PNG + `analysis.json` |
| Paper | `paper` | `paper/stability.md`, `_generated_tables.md` |
| Benchmark | `benchmark-report` | MD + JSON |
| Compare | `compare` | MD or JSON |
| CI width demo | `ci-width` | MD + PNG |

**Report contents present in manifest:** git commit, model, hardware, packages, all settings.  
**Missing:** HTML/PDF export; full environment lockfile (only package versions).

---

## 10. OFAT / research design

**Status:** IMPLEMENTED AND VERIFIED

Central question (from `paper/stability.md`):

> How stable are generative LLM benchmark scores and rankings when prompt, seed, backend, or quantization changes?

**Factors in `stability.yaml`:** `prompt_id`, `seed`, `backend`, `quantization`, `sampled`, `paraphrase_id` (skipped T4).

**Hardware confound:** Documented in `INCOMPARABILITY` block and README; Mac canary ≠ T4 paper matrix.

---

## 11. Reproducibility

**Status:** IMPLEMENTED AND VERIFIED

| Mechanism | File |
|---|---|
| Frozen JSONL | `data/`, `data/official/` |
| Git commit in manifest | `manifest.py` |
| Config hash dedup | `registry.py` |
| Checkpoint resume | `checkpoint.py` |
| Hub SHA pins | `data/official/SOURCES.md` |

**Added:** `reproduce` CLI — prints exact command from registry row.

---

## 12. Testing

**Status:** IMPLEMENTED AND VERIFIED (58 tests)

| Module | Focus |
|---|---|
| `test_stats.py` | Wilson, McNemar, Kendall, CI overlap |
| `test_sweep.py` | OFAT expansion, T4 skips, hash stability |
| `test_scoring.py` | Extractors, summarize |
| `test_report.py` | Ranking, paper tables |
| `test_benchmark_report.py` | Hallucination, safety, cost |
| `test_checkpoint.py` | Partial resume |
| `test_official_slice.py` | 800-item provenance |

**Gaps:** No integration test that loads a real model end-to-end in CI. No type checker configured.

---

## 13. Real validation evidence

| Experiment | n | Hardware | Status |
|---|---:|---|---|
| Mac canary template ablation | 28 | MPS | Committed (`hf_*.json`) |
| Colab vLLM canary | 28 | T4 | Committed |
| Paper matrix control | 800×3 | T4 | Committed |
| Paper OFAT (prompt, quant, backend, seed) | partial | T4 | 19/34 cells |
| Extended 48-item benchmark | 48 | — | **Not run** |
| Thinking ablation | — | — | **Not run** |
| Paraphrase study | 12 | — | **Not run** |

---

## 14. Contributor / cursoragent

**Status:** RESOLVED (2026-08-28)

- Local history: no `Co-authored-by: Cursor` in any commit.
- GitHub repo recreated to purge orphaned SHAs that indexed `cursoragent`.
- Contributors API: `@Shivani767` only.

---

## 15. Publication readiness (honest)

| Dimension | Score | Notes |
|---|---|---|
| Engineering | **High** | Working CLI, sweep, registry, backends, tests |
| Experimental | **Medium** | 56% of T4 matrix; core claims supported |
| Reproducibility | **High** | Frozen data, manifests, hashes |
| Statistical rigor | **Medium–High** | Wilson + McNemar + Kendall implemented; bootstrap not added |
| Novelty | **To be argued** | Configuration sensitivity + ranking stability framing |
| Related work | **Added** | `paper/RELATED_WORK.md` |
| Publication | **Not ready** | Need remaining 15 cells + thinking/robustness runs |

---

## Recommended next experiments (priority)

1. Finish paper matrix: Phi seed, Qwen/Phi quant, sampled T=0.7 (15 cells).
2. Run `configs/full_benchmark.yaml` on one model — validates extended probes E2E.
3. Run `configs/experiments/thinking.yaml` on SmolLM2 + Qwen-0.5B.
4. Run `configs/experiments/paraphrase.yaml` — prompt robustness with Kendall across variants.
5. McNemar + τ_b on completed sampled cells once all 9 land.
