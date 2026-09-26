# Experiment matrix report

- Experiment: `sarvam_application_real_eval_v1`
- Parent experiment: `sarvam_application_real_eval_v1`
- Cells: `6` successful / `6` planned
- Evaluated examples across cells: `228`
- Errors: `0`

## Baseline/candidate conclusion

- Baseline cell: `baseline`
- Candidate cell: `backend-local_transformers_dataset-data/eval_set.jsonl_model_revision-main_precision-float16_prompt_template-base_quantization-none_seed-22_split-null_task-static_qa_temperature-0.0_top_p-1.0`
- Status: **NO_MEANINGFUL_CHANGE**
- Delta (candidate - baseline): `0.0000`
- 95% bootstrap CI: `[0.0000, 0.0000]`
- Aligned examples: `38`
- Effect size: `—` (paired_cohen_dz)

## Quality summary

- Count: `6`
- Mean quality: `0.4737`
- Standard deviation: `0.0000`
- Standard error: `0.0000`
- 95% CI: `[0.4737, 0.4737]`

## Factor breakdown

| Factor | Level | Mean | n | 95% CI | Unstable |
|---|---|---:|---:|---|---|
| `backend` | `local_transformers` | 0.4737 | 228 | [0.4035, 0.5439] | False |
| `dataset` | `data/eval_set.jsonl` | 0.4737 | 228 | [0.4035, 0.5439] | False |
| `model_revision` | `main` | 0.4737 | 228 | [0.4035, 0.5439] | False |
| `precision` | `float16` | 0.4737 | 228 | [0.4035, 0.5439] | False |
| `prompt_template` | `base` | 0.4737 | 114 | [0.3947, 0.5526] | False |
| `prompt_template` | `strict` | 0.4737 | 114 | [0.3947, 0.5526] | False |
| `quantization` | `none` | 0.4737 | 228 | [0.4035, 0.5439] | False |
| `seed` | `11` | 0.4737 | 76 | [0.3553, 0.5789] | False |
| `seed` | `22` | 0.4737 | 76 | [0.3553, 0.5789] | False |
| `seed` | `33` | 0.4737 | 76 | [0.3553, 0.5789] | False |
| `split` | `None` | 0.4737 | 228 | [0.4035, 0.5439] | False |
| `task` | `static_qa` | 0.4737 | 228 | [0.4035, 0.5439] | False |
| `temperature` | `0.0` | 0.4737 | 228 | [0.4035, 0.5439] | False |
| `top_p` | `1.0` | 0.4737 | 228 | [0.4035, 0.5439] | False |

## Confidence intervals

- Across-cell mean CI: `[0.4737, 0.4737]`

## Experimental Robust Capability Score

- Mean quality: `0.4737`
- Configuration variance: `0.0000`
- Lambda: `1.0000`
- RCS: `0.4737`
- Experimental: `True`

## Unstable conditions

- None identified.

## Representative sensitive failures

- None identified.

## Reproduction

`apertus-eval-prep platform-matrix --config runs/phase8_real_colab/configs/local_variance.yaml`

## Limitations

- Synthetic/mock cells are evidence of platform behavior, not model quality
- RCS is an experimental project-defined score, not a universal benchmark metric
- Small or incomplete matrices should be interpreted as inconclusive
- Synthetic/mock cells validate platform behavior only; they are not real model benchmark results.
