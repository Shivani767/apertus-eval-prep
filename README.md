# apertus-eval-prep

A reproducible evaluation harness for studying how benchmark outcomes and rankings change under realistic configuration shifts: chat template, backend, prompt format, quantization, sampling, and hardware.

This project is designed as a research artifact, not a leaderboard generator. The goal is to make configuration-sensitive evaluation auditable: every run is frozen with YAML, a registry row, and a git commit, so that a claimed result can be replayed and compared rather than merely reported.

## Research question

How much do benchmark scores and model rankings change when the evaluation pipeline changes, even when the underlying model and task slice are held fixed?

The project treats evaluation configuration as part of the measurement. A model score is therefore reported as a tuple of model × task slice × backend × prompt format × decoding settings × hardware, not as an isolated scalar.

## Current verified status

The repository now includes the downloaded paper-result archive and the sampled outputs already present in the project results folder. The verified matrix status is:

- 23 / 34 paper-matrix cells completed
- 11 cells remain
- sampled cell 21 is included in the repository archive

Primary artifacts:
- [results/registry_paper.jsonl](results/registry_paper.jsonl)
- [results/paper_matrix_partial.zip](results/paper_matrix_partial.zip)
- [results/runs](results/runs)

## Research design

The project isolates one factor at a time and stores the result as a replayable registry entry. The core variables are:

- model family and revision
- task slice and prompt specification
- chat template mode
- backend (HF generate vs vLLM)
- quantization (int8 / int4)
- decoding temperature and seed
- hardware and runtime configuration

This makes it possible to distinguish between:
- genuine model capability changes,
- serving configuration changes,
- formatting or template drift,
- downstream non-comparability caused by hardware or decoding differences.

## Key findings from the committed runs

### 1. Prompt format changes score materially

For the three-model control cohort, the prompt specification moves accuracy in a way that is larger than noise and is therefore scientifically relevant.

| model | control | concise | 5-shot |
|---|---:|---:|---:|
| SmolLM2 | 318 | 186 | 274 |
| Qwen-3B | 515 | 410 | 549 |
| Phi-3.5 | 536 | 471 | 451 |

This suggests that prompt formatting is not a minor implementation detail; it changes the measured outcome and under some conditions changes the model ordering.

### 2. Backend differences are observable even with identical rendered strings

Same task slice, same prompt payload, same model, different serving stack.

| backend | SmolLM2 | Qwen-3B | Phi-3.5 |
|---|---:|---:|---:|
| HF generate | 318 | 515 | 536 |
| vLLM | 336 | 534 | 537 |

These differences are not dismissed as noise; they are evidence that backend and serving stack must be treated as part of the experiment definition.

### 3. Quantization does not show a strong, stable degradation in the available evidence

The committed SmolLM2 quantization checks remain within the range of the fp16 control for this setup, which reinforces the caution that a single model and a single factor cannot support broad claims about quantization quality without a matched control and a larger sweep.

### 4. The sampled cells are part of the same experimental record

The downloaded sampled archive includes the completed sampled runs for the SmolLM2 study path and is now included in the repo artifact set. This is part of the same evidence stream used for the paper matrix and should be interpreted as a committed result, not as an ad hoc notebook output.

## Results and papers

The project publishes the results through the registry and generated analysis documents rather than by hard-coding values into prose. The relevant outputs are:

- [paper/run_status.md](paper/run_status.md)
- [paper/_generated_tables.md](paper/_generated_tables.md)
- [reports/stability_paper/stability.md](reports/stability_paper/stability.md)
- [results/registry_paper.jsonl](results/registry_paper.jsonl)

## Experimental protocol

The study follows a strict protocol:

1. freeze the benchmark slice,
2. freeze the model revision,
3. vary exactly one factor,
4. record the config hash and git commit,
5. compare only runs that share the same task and measurement definition.

This avoids the common failure mode where comparison tables silently mix prompt templates, backends, decoding settings, hardware, and data slices.

## Reproducibility

```bash
git clone https://github.com/Shivani767/apertus-eval-prep
cd apertus-eval-prep
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
python -m apertus_eval_prep eval --config configs/smoke.yaml --out results/smoke.json
```

Additional artifact regeneration:

```bash
make paper
make figures
```

## Remaining work

The remaining open work is clearly bounded:

- Phi quantization cells (cell 14)
- remaining sampled cells in the paper matrix

The project is no longer using a loose task list; it is a tracked research status with committed result artifacts and explicit remaining cells.

## License

Apache-2.0. See [LICENSE](LICENSE).
