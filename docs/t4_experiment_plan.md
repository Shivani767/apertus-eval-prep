# T4 Research Experiment Plan (zero-paid-GPU constraint)

**Status: PLAN — no real experiment has been launched from this document yet.**
Every number below is a *design specification*, not a measurement. The measured
results will live in `results/registry_t4.jsonl` and will be labeled
`measured` once they exist.

## 0. Constraint

All real inference must fit a free Google Colab T4 (16 GB, ephemeral session).
All statistical analysis (variance decomposition, held-out reliability,
budget replay, LOMO, figures) runs offline on the local MacBook CPU from the
persisted registry — zero GPU cost per analysis, and replay repetitions are
free, so uncertainty bands come from many repetitions, not one lucky run.

## 1. Selected models

Chosen from `configs/experiments/stability.yaml` (existing support, existing
runs in `results/registry_paper.jsonl`, no new model families):

| model | params | T4 fit (fp16 / int8) | role |
|---|---|---|---|
| `HuggingFaceTB/SmolLM2-1.7B-Instruct` | 1.7B | both easy | Stage 1 ground truth |
| `Qwen/Qwen2.5-3B-Instruct` | 3B | fp16 ~6 GB, int8 ~4 GB | Stage 2 |
| `microsoft/Phi-3.5-mini-instruct` | 3.8B | fp16 ~8 GB, int8 ~5 GB | Stage 2 |

`Qwen/Qwen2.5-7B-Instruct` is explicitly excluded (fp16 ≈ 14 GB + activations
is unsafe on a shared T4; the existing `profiles.t4.skip` list already excludes
it). No new model family is added.

## 2. Benchmark

ONE benchmark slice: the existing frozen `data/official/eval_set.jsonl`
(800 items) restricted to `tasks: [arc_easy, gsm8k]` with `limit: 100`
per task (200 scored items per configuration). Rationale: 4 tasks × full
items × 27 configs × 3 models does not fit a free T4 session; 2 tasks × 100
keeps the per-config wall time small enough for resumable sessions while
preserving exact-match scoring on the frozen slice. The dataset is frozen
(same files, same hashes) across every configuration; the *configuration*
factors vary, never the data.

## 3. Configuration factors (per model)

| factor | levels | field |
|---|---|---|
| prompt P | `default` (P0), `concise` (P1), `5shot` (P2) | `prompt_id` |
| backend B | `hf` (B0), `vllm` (B1) | `backend` |
| quantization/runtime Q | `none` (Q0), `int8` (Q1) | `quantization` |
| seed S | `0`, `1`, `2` | `seed` |

The 36-cell Cartesian (3 prompts × 2 backends × 2 quantization × 3 seeds) is
**structurally impossible**: this harness refuses vLLM×int8 (bitsandbytes
quantization is HF-only), so a B×Q cell would confound the two factors
(`configs/experiments/t4_factorial.yaml` header). The honest design is a
**nested factorial with a composite runtime factor**:

runtime R (3 levels) = (hf, none) | (hf, int8) | (vllm, none), crossed with
prompt P (3 levels: `default`, `concise`, `5shot`) and seed S (3 levels:
0, 1, 2) → 3 × 3 × 3 = **27 configurations per model**
(`factorial_only_combos` in the YAML — explicit allow-list, auditable).

Measurable two-way designs: Prompt×Runtime (full 3×3, seed replication →
residual SS), Prompt×Quantization at backend=hf (3×2), Prompt×Backend at
quantization=none (3×2). Backend×Quantization is reported UNAVAILABLE —
never improvised. All prompt levels already exist
(`configs/prompts/{default,concise,5shot}.yaml`);
`VALID_BACKENDS = {hf,vllm}`, `VALID_QUANTIZATION = {none,int8}`. No
fabricated level. If a specific
(model × backend × quantization) cell fails at runtime (e.g. vLLM cannot serve
a given revision on T4), the cell is recorded as a *failed configuration* in
the registry with its error — never silently skipped — and the analysis
reports the design as incomplete for that model (the guarded variance code
refuses unbalanced decompositions rather than improvising).

## 4. Exact configuration count

- Stage 0 (local, no GPU): 27 × 3 = 81 cells generated, hashed, checked for
  duplicates, resume replayed — zero inference.
- Stage 1 (T4): SmolLM2-1.7B × 27 = **27 real configurations**.
- Stage 2 (T4, only after Stage 1 validation): Qwen2.5-3B and Phi-3.5-mini × 27
  each. If session budget does not allow, the documented fallback is the
  18-config design (same prompt × runtime grid, seeds [0, 1]; see §10); the
  design change is recorded in the registry (`design` field) and never applied
  silently.

## 5. Runtime considerations (measured-then-scaled)

Per-configuration cost ≈ (load model once per session) + 200 items × up to
256 new tokens. Rough T4 expectation for SmolLM2-1.7B fp16: ~1–3 min/config;
int8 and vLLM cells similar or faster; Qwen/Phi ~2–4× slower. The 27-cell
study is plausibly one Colab session for Stage 1 — but **no time estimate is
authoritative until `--dry-run` plus one measured configuration exist** (§7
requires measuring before scaling). The runner prints measured mean
seconds/config and extrapolates only from that.

## 6. Checkpointing / resume

Already implemented and reused verbatim (`sweep.execute_cells`):
- after EVERY configuration: run JSON written, registry row appended
  (`results/registry_t4.jsonl`) — the registry is append-only JSONL, so a
  killed session leaves a valid partial registry;
- resume = re-running the same command: `completed_hashes()` skips every
  `config_hash` already present; no completed configuration is re-run;
- per-run item checkpoints (`*.partial.jsonl`) survive mid-configuration
  interruption via `run_eval(checkpoint_path=...)`;
- failures are recorded — never silently skipped.

## 7. Memory / runtime safety protocol

`scripts/run_t4_research.py` enforces, in order:
1. `--dry-run`: enumerate + hash all 27 configs, no model load;
2. memory smoke: load ONE model, run ONE control configuration, record peak
   memory + wall time, verify non-null accuracy, free the model;
3. only then continue with the remaining configurations (batch size 1,
   model reused across cells of one model, explicit cleanup between models).

## 8. Statistical plan (offline, CPU)

- **Variance decomposition**: guarded two-way decomposition
  (`variance.factorial_variance_decomposition`) on complete+balanced cell
  designs only: Prompt×Backend, Prompt×Quantization, Backend×Quantization
  (seed replication within cells → residual SS). omega² effect sizes,
  bootstrap CIs (seeded), assumptions recorded. Incomplete/unbalanced →
  status UNAVAILABLE + reason, never forced.
- **Ranking stability**: Kendall tau / Spearman between per-configuration
  rankings; rank-reversal probability over configurations.
- **Held-out reliability** (`heldout.*`): deterministic seeded train/holdout
  splits at budgets {5, 10, 15, 20, 25, 30}; estimator fit on train cells
  ONLY; calibration (ECE/Brier/log-loss/AUROC), pairwise decision accuracy,
  reliability error, CI coverage vs actual holdout outcomes.
- **Budget replay / curves** (`adaptive.budget_curves`): Random (many seeded
  trajectories), OFAT, Apertus-R — all reading the SAME frozen ground-truth
  pool; metrics: ranking recovery (Kendall tau vs full-space ranking),
  pairwise decision accuracy, reversal rate, score MAE, cost.
- **LOMO generalization probe** (only when ≥3 models measured): existing
  `leave_one_model_out_*`; explicitly labeled a low-power probe.
- Hypotheses H1–H4 get verdicts from these analyses only (§9); no method
  tuning on held-out outcomes.

## 9. Hypotheses (registered a priori; no assumed truth)

- **H1**: Apertus-R achieves higher ranking recovery than Random at equal
  budgets. Verdict from budget-curve comparison with bootstrap CIs.
- **H2**: Reliability estimated from observed configs predicts held-out
  ranking stability. Verdict from calibration/accuracy on holdout cells.
- **H3**: Configuration factors exhibit interaction effects. Verdict from
  guarded factorial decompositions; "meaningful" declared *before* looking:
  interaction fraction ≥ 5% of total SS for this small design.
- **H4**: A limited budget recovers the full-space ranking with substantially
  fewer measurements. Verdict from recovery-vs-budget curves (smallest budget
  reaching mean recovery ≥ 0.9).

Each verdict may be SUPPORTED, NOT SUPPORTED, or INCONCLUSIVE; negative
results are preserved and reported.

## 10. Reduced confirmation design (documented fallback, NOT default)

If Stage 2 sessions run out of budget: 18 configs/model = full 2×2×2
backend×quantization×prompt core on seed 0 (8 cells), seed-1 and seed-2
replications of the backend×quantization core at P0 (8 cells), and
P1/P2 × hf × none × seed 0 (2 cells). Keeps B×Q fully replicated and prompt
marginals exact. Any use of the reduced design is written into the registry
row (`design` field) and the analysis reports it.

## 11. Expected outputs

- `results/registry_t4.jsonl` (+ `results/runs_t4/*.json` per config)
- `reports/t4/{variance,interactions,heldout,budget_curves,lomo,hypotheses}.json`
- `reports/t4/summary.md` — human summary with status labels
- figures (script-generated from the registry, only if data supports them):
  budget-vs-recovery (primary), variance decomposition, interaction effects,
  ranking stability, calibration.

## 12. Limitations

- One benchmark, 2 tasks, 200 items: configuration effects measured here do
  not automatically transfer to other benchmarks; "ground-truth within the
  evaluated configuration space" is literal.
- 3 models from 2 families: ranking claims are about these models only.
- vLLM-on-T4 coverage: if vLLM cannot serve some model, that factor collapses
  to a documented unavailable level rather than a fabricated result.
- Seed as a "factor" under greedy decoding may be a no-op (deterministic
  generation): zero seed variance is a valid finding, reported honestly.
- LOMO with 3 models is a probe, not evidence of generalization.
- Free-T4 sessions may die mid-run; resume is by design, but wall-clock
  estimates remain extrapolations until measured.


