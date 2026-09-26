# Experiment matrix report

- Experiment: `sarvam_application_real_eval_v1`
- Parent experiment: `sarvam_application_real_eval_v1`
- Cells: `6` successful / `6` planned
- Evaluated examples across cells: `0`
- Errors: `0`

## Baseline/candidate conclusion

- Baseline cell: `None`
- Candidate cell: `None`
- Status: **INCONCLUSIVE**
- Delta (candidate - baseline): `—`
- 95% bootstrap CI: `[—, —]`
- Aligned examples: `0`
- Effect size: `—` (paired effect)

## Quality summary

- Count: `0`
- Mean quality: `—`
- Standard deviation: `—`
- Standard error: `—`
- 95% CI: `[—, —]`

## Factor breakdown

| Factor | Level | Mean | n | 95% CI | Unstable |
|---|---|---:|---:|---|---|

## Confidence intervals

- Across-cell mean CI: `[—, —]`

## Experimental Robust Capability Score

- Mean quality: `—`
- Configuration variance: `—`
- Lambda: `1.0000`
- RCS: `—`
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
