# Experiment matrix report

- Experiment: `sarvam_application_real_eval_v1`
- Parent experiment: `sarvam_application_real_eval_v1`
- Cells: `2` successful / `2` planned
- Evaluated examples across cells: `2`
- Errors: `0`

## Baseline/candidate conclusion

- Baseline cell: `baseline`
- Candidate cell: `backend-local_transformers_dataset-data/platform_episodes.jsonl_model_revision-main_precision-float16_prompt_template-base_quantization-none_seed-11_split-null_task-agent_episode_temperature-0.0_top_p-1.0`
- Status: **INCONCLUSIVE**
- Delta (candidate - baseline): `0.0000`
- 95% bootstrap CI: `[0.0000, 0.0000]`
- Aligned examples: `1`
- Effect size: `—` (paired_cohen_dz)

## Quality summary

- Count: `2`
- Mean quality: `0.0000`
- Standard deviation: `0.0000`
- Standard error: `0.0000`
- 95% CI: `[0.0000, 0.0000]`

## Factor breakdown

| Factor | Level | Mean | n | 95% CI | Unstable |
|---|---|---:|---:|---|---|
| `backend` | `local_transformers` | 0.0000 | 2 | [0.0000, 0.0000] | False |
| `dataset` | `data/platform_episodes.jsonl` | 0.0000 | 2 | [0.0000, 0.0000] | False |
| `model_revision` | `main` | 0.0000 | 2 | [0.0000, 0.0000] | False |
| `precision` | `float16` | 0.0000 | 2 | [0.0000, 0.0000] | False |
| `prompt_template` | `base` | 0.0000 | 2 | [0.0000, 0.0000] | False |
| `quantization` | `none` | 0.0000 | 2 | [0.0000, 0.0000] | False |
| `seed` | `11` | 0.0000 | 2 | [0.0000, 0.0000] | False |
| `split` | `None` | 0.0000 | 2 | [0.0000, 0.0000] | False |
| `task` | `agent_episode` | 0.0000 | 1 | [0.0000, 0.0000] | False |
| `task` | `rag_episode` | 0.0000 | 1 | [0.0000, 0.0000] | False |
| `temperature` | `0.0` | 0.0000 | 2 | [0.0000, 0.0000] | False |
| `top_p` | `1.0` | 0.0000 | 2 | [0.0000, 0.0000] | False |

## Confidence intervals

- Across-cell mean CI: `[0.0000, 0.0000]`

## Experimental Robust Capability Score

- Mean quality: `0.0000`
- Configuration variance: `0.0000`
- Lambda: `1.0000`
- RCS: `0.0000`
- Experimental: `True`

## Unstable conditions

- None identified.

## Representative sensitive failures

- None identified.

## Reproduction

`apertus-eval-prep platform-matrix --config runs/phase8_real_colab/configs/local_rag_agent.yaml`

## Limitations

- Synthetic/mock cells are evidence of platform behavior, not model quality
- RCS is an experimental project-defined score, not a universal benchmark metric
- Small or incomplete matrices should be interpreted as inconclusive
- Synthetic/mock cells validate platform behavior only; they are not real model benchmark results.
