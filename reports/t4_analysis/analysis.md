# T4 research analysis (data label: measured)

- registry: `results/registry_paper.jsonl`
- generated: 2026-09-12T15:25:52+00:00
- usable observations: 31 of 31 registry rows (0 problems reported)

## Configuration coverage per model

| model | configs | unique | levels (b/p/q/s) |
|---|---|---|---|
| HuggingFaceTB/SmolLM2-1.7B-Instruct | 11 | 8 | 2/3/3/3 |
| Qwen/Qwen2.5-3B-Instruct | 11 | 8 | 2/3/3/3 |
| Qwen/Qwen2.5-7B-Instruct | 1 | 1 | 1/1/1/1 |
| microsoft/Phi-3.5-mini-instruct | 8 | 8 | 2/3/3/3 |

## Factorial variance decomposition (guarded ANOVA, per model)

- HuggingFaceTB/SmolLM2-1.7B-Instruct prompt_idxbackend: UNAVAILABLE — ANOVA requires a complete, balanced design; rerun as a balanced factorial (see interaction.interaction_design)
- HuggingFaceTB/SmolLM2-1.7B-Instruct prompt_idxquantization: UNAVAILABLE — ANOVA requires a complete, balanced design; rerun as a balanced factorial (see interaction.interaction_design)
- HuggingFaceTB/SmolLM2-1.7B-Instruct backendxquantization: UNAVAILABLE — ANOVA requires a complete, balanced design; rerun as a balanced factorial (see interaction.interaction_design)
- Qwen/Qwen2.5-3B-Instruct prompt_idxbackend: UNAVAILABLE — ANOVA requires a complete, balanced design; rerun as a balanced factorial (see interaction.interaction_design)
- Qwen/Qwen2.5-3B-Instruct prompt_idxquantization: UNAVAILABLE — ANOVA requires a complete, balanced design; rerun as a balanced factorial (see interaction.interaction_design)
- Qwen/Qwen2.5-3B-Instruct backendxquantization: UNAVAILABLE — ANOVA requires a complete, balanced design; rerun as a balanced factorial (see interaction.interaction_design)
- Qwen/Qwen2.5-7B-Instruct prompt_idxbackend: UNAVAILABLE — need >= 2 levels per axis and >= 4 crossed cells
- Qwen/Qwen2.5-7B-Instruct prompt_idxquantization: UNAVAILABLE — need >= 2 levels per axis and >= 4 crossed cells
- Qwen/Qwen2.5-7B-Instruct backendxquantization: UNAVAILABLE — need >= 2 levels per axis and >= 4 crossed cells
- microsoft/Phi-3.5-mini-instruct prompt_idxbackend: UNAVAILABLE — ANOVA requires a complete, balanced design; rerun as a balanced factorial (see interaction.interaction_design)
- microsoft/Phi-3.5-mini-instruct prompt_idxquantization: UNAVAILABLE — ANOVA requires a complete, balanced design; rerun as a balanced factorial (see interaction.interaction_design)
- microsoft/Phi-3.5-mini-instruct backendxquantization: UNAVAILABLE — ANOVA requires a complete, balanced design; rerun as a balanced factorial (see interaction.interaction_design)

## Pairwise ranking stability (within measured configs)

- HuggingFaceTB/SmolLM2-1.7B-Instruct vs Qwen/Qwen2.5-3B-Instruct: A wins 0.000 of 8 shared configs; flip probability 0.000
- HuggingFaceTB/SmolLM2-1.7B-Instruct vs Qwen/Qwen2.5-7B-Instruct: insufficient shared configs
- HuggingFaceTB/SmolLM2-1.7B-Instruct vs microsoft/Phi-3.5-mini-instruct: A wins 0.000 of 8 shared configs; flip probability 0.000
- Qwen/Qwen2.5-3B-Instruct vs Qwen/Qwen2.5-7B-Instruct: insufficient shared configs
- Qwen/Qwen2.5-3B-Instruct vs microsoft/Phi-3.5-mini-instruct: A wins 0.125 of 8 shared configs; flip probability 0.250
- Qwen/Qwen2.5-7B-Instruct vs microsoft/Phi-3.5-mini-instruct: insufficient shared configs

## Budget replay (offline; identical budgets across strategies)

- budget 5: apertus_r 0.990 [0.800, 1.000]; ofat 1.000 [1.000, 1.000]; random 0.650 [-1.000, 1.000]
- budget 10: apertus_r 0.940 [0.800, 1.000]; ofat 1.000 [1.000, 1.000]; random 0.865 [0.500, 1.000]
- budget 15: apertus_r 0.960 [0.800, 1.000]; ofat 1.000 [1.000, 1.000]; random 0.850 [0.500, 1.000]
- budget 20: apertus_r 1.000 [1.000, 1.000]; ofat 0.800 [0.800, 0.800]; random 0.940 [0.800, 1.000]
- budget 25: apertus_r 1.000 [1.000, 1.000]; ofat 1.000 [1.000, 1.000]; random 1.000 [1.000, 1.000]

## Held-out configuration reliability (estimator: train only)

- budget 5: decision acc None, kendall 0.3333333333333333, ECE None, CI coverage None

## Leave-one-model-out (generalization probe)

- budget 5: hidden model #2, visible decision acc 1.0

## Provenance

- git commits: ['0022b2bed8a91e4d9a121763610f073e76dcb53a', '039cf37e32d8f33d11c276949cf74204bcd4df13', '1c8a4dabafb1eda3b03a85674059e8d2e383b0b5', '33bcec9fb66dc75dc6c5a40774994bacb0d8c009', '33c582c7de8dd18bc78f05c803b353dbd1808c22', '580ab82775b16407d5a97073de7c9df7883d0612', '58dcd892f836c0d57cc8b783c571b220b729dce5', '6c8c9c433e0076203fdbcaa6b40b886f002f9203', '8555f7f25375a0fcd913d5ee3ffa825eb4361e97', 'daa243d6212bedbd692484b30fe77d6512f7cbe1', 'ebf46a0d477ec55f8229a3cbc80d709305fee6c2', 'ec364b645b1d3d09c3eeec3247d65a819e37872b', 'f76d8f7e89876303f4bd1a2f20c06926bce1d059', 'fba3f21c5627c71f1b7803954e5113b3a603918e']
- rows missing git commit: 0
- window: 2026-08-20T15:58:16Z .. 2026-09-10T15:14:54Z

_Data label: measured. All tables/figures derived from the registry at the path above; held-out rows are held-out, LOMO rows are OOD probes. Ground truth means 'within the evaluated configuration space'._
