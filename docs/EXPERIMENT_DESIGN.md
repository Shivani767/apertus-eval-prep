# Experiment design

Declare an experiment with a shared typed run spec and named factors:

```yaml
experiment:
  name: variance-study
  id: variance-study
  base:
    adapter: {kind: mock, model_id: synthetic/mock-oracle-v1}
    task: {kind: static_qa, path: data/platform_smoke.jsonl}
  baseline: {seed: 1, temperature: 0.0}
  factors:
    seed: [1, 2, 3]
    temperature: [0.0, 0.2]
    prompt_id: [base, strict]
  max_runs: 32
```

Expansion is deterministic, baseline first, with independent child artifacts and a shared experiment ID. `max_runs` prevents accidental Cartesian explosions. Missing or failed cells appear in the report with a reason; they are not silently replaced by zero.

For a valid comparison, freeze dataset bytes, task filters, prompt/evaluator definitions, and scoring semantics. Treat seed, prompt, decoding, backend, and quantization as explicit factors. Inspect factor-level spreads, per-example condition sensitivity, failed-run coverage, and the RCS components together. A single aggregate score is not evidence of robustness.


## Phase 8 study design

`configs/studies/phase8_real_model_study.yaml` is a fillable real-model template; `phase8_mock_study.yaml` is explicitly synthetic CI validation. A real evidence mode rejects a mock adapter unless the separate `allow_mock` demonstration flag is set. Use `platform-study-analyze` only after compatible child artifacts exist, and record deviations before interpreting comparisons. Study reports are descriptive and do not establish causal or production claims.

After a matrix run, use `platform-report` for a release-review report and `platform-fingerprint` for observed failure-pattern aggregation. The parent report and each child artifact remain separate; the fingerprint is derived evidence, not a causal explanation.
