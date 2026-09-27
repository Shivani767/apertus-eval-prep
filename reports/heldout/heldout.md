# Held-out configuration generalization (DERIVED)

Source registry: `results/registry_paper.jsonl`. 3 models x 11 configurations (3 missing cell(s), left None).

No new measurement: every value is derived from committed registry rows. For each budget the estimator is fit on the train configurations only; held-out configurations are used for evaluation and never for fitting.

| runs spent | held out | score error (MAE) | rank recovery (kendall) | decision acc | decidable pairs |
|---:|---:|---:|---:|---:|---:|
| 2 | 9 | 0.0298 | 1.000 | 1.000 | 6 |
| 3 | 8 | 0.0266 | 1.000 | 1.000 | 6 |
| 4 | 7 | 0.0382 | 1.000 | 1.000 | 6 |
| 5 | 6 | 0.0194 | 0.333 | 1.000 | 6 |
| 6 | 5 | 0.0456 | 0.333 | 1.000 | 6 |
| 7 | 4 | 0.0239 | 1.000 | 1.000 | 6 |
| 8 | 3 | 0.0223 | 1.000 | 1.000 | 6 |
| 9 | 2 | 0.0158 | 1.000 | 1.000 | 6 |
| 10 | 1 | 0.0177 | 1.000 | 1.000 | 6 |

score error (MAE): mean |train mean - holdout mean| accuracy, per model. rank recovery: Kendall tau between the train ranking and the holdout ranking. decision acc: how often the train winner is also the holdout winner, over pairs where both sides decide.

Reading: a plateau near 0 error and 1.0 accuracy means the matrix already predicts its own remainder; values far from those are the honest cost of an under-sampled configuration space.

## Rank instability across configurations

| model A | model B | A wins | B wins | reversible | B wins only on |
|---|---|---:|---:|---|---|
| HuggingFaceTB/SmolLM2-1.7B-Instruct | Qwen/Qwen2.5-3B-Instruct | 0 | 11 | no | backend=vllm, control=control, prompt_id=5shot, prompt_id=concise, quantization=int4, quantization=int8, sampled=t0.7_seed0, sampled=t0.7_seed1, sampled=t0.7_seed2, seed=1, seed=2 |
| HuggingFaceTB/SmolLM2-1.7B-Instruct | microsoft/Phi-3.5-mini-instruct | 0 | 8 | no | backend=vllm, control=control, prompt_id=5shot, prompt_id=concise, quantization=int4, quantization=int8, seed=1, seed=2 |
| Qwen/Qwen2.5-3B-Instruct | microsoft/Phi-3.5-mini-instruct | 1 | 7 | yes | backend=vllm, control=control, prompt_id=concise, quantization=int4, quantization=int8, seed=1, seed=2 |

A high decision accuracy above does NOT mean the ranking is safe. A reproducible minority of configurations can overturn an ordering without moving the majority vote, so the minority column is the one to read: those configuration keys are where a stable-looking ranking fails.
