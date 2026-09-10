# Research plan — "When Can We Trust an LLM Benchmark?"

Status model for every claim below: **MEASURED** (committed run JSON) /
**DERIVED** (computed from measured, code + version recorded) /
**PENDING** (infrastructure exists, measurement missing) /
**UNAVAILABLE** (not measurable here). Never fabricate; never overwrite verified rows.

## Central question

An LLM benchmark score is an observation of
`model + task + protocol + runtime`, not a pure property of the model.
We study how scores and rankings move under reasonable protocol changes.

## RQs and hypotheses

- RQ1 (sensitivity): prompt/prompt-family/few-shot/sampling/seed/backend/quant/
  inference-config/hardware/task/model perturbations move scores. H: prompt and
  sampling move scores most on generative exact-match; seed with greedy decode is ~no-op.
- RQ2 (ranking): reasonable changes flip model ranks. H: control Phi vs Qwen-3B is a
  CI-overlap tie; 5-shot already flips the point ranking (tau_b=0.3333, 1 reversal).
- RQ3 (variance attribution): which factors explain the most variance. H: prompt >
  sampled > backend > quant on this matrix (to be tested by decomposition, Phase 6).
- RQ4 (predictability): fragility predictable from metadata + history. H: not with
  n=31 rows — build interface + tests, mark UNVALIDATED until data suffices.
- RQ5 (adaptivity): adaptive selection reaches ranking confidence with fewer cells
  than exhaustive OFAT. H: uncertainty sampling beats random; prove vs baselines.

## Variables / controls

Independent: prompt_id/family/version, few-shot, temperature/top_p/seed, backend(+version),
quant/dtype, max_new_tokens, chat_template, paraphrase_id, hardware, task slice, model(+revision).
Controls: frozen `data/official/*.jsonl` (n=200/task), fixed gold extractor
(`scoring.py`), greedy control (T=0, seed 0), tokenizer template, HF backend unless
the factor under test. Recorded per run in `manifest.settings` + `hardware` + `packages`.

## Experiment matrix (T4, 34 cells, 31 MEASURED / 3 PENDING)

From `configs/experiments/stability.yaml` profile `t4`:
control x3, prompt_id x6, quantization x7 (incl. 7B int4), backend x3, seed x6,
sampled x9. PENDING: Phi `sampled` t0.7_seed0/1/2. Paraphrase skipped on T4 by design.
Multi-factor (Phase 5): Prompt x Backend, Prompt x Quant, Backend x Quant, 3-way —
opt-in factorial with budget caps, never brute-force Cartesian.

## Metrics / tests

Score: accuracy + Wilson 95% CI; paired McNemar (continuity-corrected) vs control.
Stability (`stability.py`): variance/range/std/CV/bootstrap-CI/paired-diff/Cohen-h
+ per-factor sensitivities. Ranking (`ranking.py`): Kendall tau (existing) +
Spearman, win-rates, rank distribution, P(#1), mean/var rank, reversals, bootstrap
rank stability. Fragility: components first, then provisional EFI with documented
formula/normalization/ablations. Variance: ANOVA only where assumptions hold;
variance-components/mixed-effects where justified, else descriptive decomposition.

## Threats to validity

T4-only hardware; n=800 generative exact-match (not loglikelihood); greedy seeds
may be no-ops; single paraphrase set; no interaction estimates in OFAT; small-n
ranking claims need CI-aware ties; cost is estimated unless metered.

## Artifacts per experiment

Config snapshot + git commit + manifest + run JSON + registry row + analysis JSON
+ report section + figures/tables. `make paper` / `make figures` regenerate;
hand status (`paper/run_status.md`) cites registry counts only.
