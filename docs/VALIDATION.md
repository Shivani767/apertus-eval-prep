# Validation experiment (2026-08-28)

End-to-end pipeline validation using **committed scored JSON** — no fabricated numbers.

## Command

```bash
python -m apertus_eval_prep benchmark-report \
  --run results/hf_tokenizer.json=Mac-canary \
  --run results/runs/SmolLM2-1.7B-Instruct_control_control_24ffe98d9250761d.json=SmolLM2-control \
  --run results/runs/SmolLM2-1.7B-Instruct_quantization_int8_46dd44d463433c26.json=SmolLM2-int8 \
  --out reports/validation
```

**Pipeline exercised:** load JSON → multi-model comparison → quantization derived metrics → McNemar pairing → Pareto → MD + JSON report.

## Results (from `reports/validation/benchmark.json`)

### Multi-model (note: different slices — canary n=28 vs paper n=800; do not pool)

| Label | Model | Overall acc | 95% Wilson CI |
|---|---|---:|---|
| Mac-canary | Qwen2.5-0.5B | 0.714 | — |
| SmolLM2-control | SmolLM2-1.7B | 0.398 | [0.364, 0.432] |
| SmolLM2-int8 | SmolLM2-1.7B | 0.418 | [0.384, 0.452] |

### Quantization (same model, paired n=800, T4)

| Metric | Value |
|---|---:|
| fp16 accuracy | 0.3975 |
| int8 accuracy | 0.4175 |
| accuracy_delta_pp | +2.0 |
| fp16 tokens/sec | 23.8 |
| int8 tokens/sec | 7.4 |
| throughput_change_ratio | −0.69 |
| McNemar n | 800 |
| McNemar p | 0.11 (not significant vs fp16 control) |

### Reproduce CLI

```bash
python -m apertus_eval_prep reproduce \
  --run-id SmolLM2-1.7B-Instruct_control_control_24ffe98d9250761d \
  --registry results/registry_paper.jsonl
```

Returns sweep replay command + git commit `ec364b64…` from manifest.

## Not validated in this run

- Thinking mode (no paired runs loaded)
- Paraphrase robustness (study not run)
- Extended 48-item probe suite (hallucination/safety/robustness)
- GPU inference in CI (uses pre-committed JSON)

## Tests

58 unit tests pass (`pytest -q`) including new `test_analysis.py`, `test_reproduce.py`.
