# CLI Reference

Every command and option below was verified by running `--help` against this repository at
the release commit. Nothing here is aspirational: if a command is not in this document, it
does not exist.

Two equivalent invocations are available:

```bash
apertus-eval-prep <command> ...               # console script, after pip install -e .
python -m apertus_eval_prep <command> ...     # equivalent, no install required
```

`apertus-eval-prep --help` lists 30 commands in two families:

- **`platform-*`** — the typed platform (Phases 1–8). Immutable artifacts, evidence modes,
  identity checks.
- **legacy research harness** — the original frozen-prompt harness. Still supported and
  tested, but its artifacts predate the evidence-mode system (see
  [Evidence and Claim Boundaries](METHODOLOGY.md#evidence-and-claim-boundaries)).

## Command index

### Typed platform

| Command | Purpose | GPU/network |
|---|---|---|
| [`platform-run`](#platform-run) | Run a typed evaluation, write immutable artifacts | only with a real adapter |
| [`platform-matrix`](#platform-matrix) | Expand and run a deterministic experiment matrix | only with a real adapter |
| [`platform-compare`](#platform-compare) | Paired comparison of two run directories | no |
| [`platform-episode`](#platform-episode) | RAG / agent episode evaluation | only with a real adapter |
| [`platform-safety`](#platform-safety) | Sanitized offline safety suite | only with a real adapter |
| [`platform-report`](#platform-report) | Rebuild Markdown/HTML reports from a run | no |
| [`platform-fingerprint`](#platform-fingerprint) | Rebuild `failure_fingerprint.json` | no |
| [`platform-gate`](#platform-gate) | Evaluate release gates | no |
| [`platform-export-review`](#platform-export-review) | Export a sanitized review package | no |
| [`platform-ingest-review`](#platform-ingest-review) | Validate annotations, compute agreement | no |
| [`platform-study-analyze`](#platform-study-analyze) | Aggregate compatible runs into a study report | no |
| [`platform-ingest-runs`](#platform-ingest-runs) | Convert runs into deployment comparison points | no |
| [`platform-select`](#platform-select) | Pareto frontier and constraint-based selection | no |

### Legacy research harness

| Command | Purpose | GPU/network |
|---|---|---|
| [`eval`](#legacy-harness) | Score a frozen slice | with a real backend |
| [`compare`](#legacy-harness) | Diff two eval JSON files | no |
| [`sweep`](#legacy-harness) | Expand OFAT cells and run | with a real backend |
| [`report`](#legacy-harness) | CIs, Kendall tau, plots from a registry | no |
| [`experiment`](#legacy-harness) | config → sweep → stats → report | with a real backend |
| [`reproduce`](#legacy-harness) | Print a replay command from a registry row | no |
| [`ers`](#legacy-harness) | Evaluation Reliability Score | no |
| [`pareto`](#legacy-harness) | Accuracy vs cost frontier | no |
| [`failures`](#legacy-harness) | Failure taxonomy | no |
| [`profile`](#legacy-harness) | Runtime/token profile | no |
| [`dashboard`](#legacy-harness) | Aggregate research report | no |
| [`site`](#legacy-harness) | Export `site.json` for the research site | no |
| [`catalog`](#legacy-harness) | Dataset fingerprints and model coverage | no |
| [`dump-prompts`](#legacy-harness) | Render prompts with special tokens visible | no |
| [`paper-tables`](#legacy-harness) | Write paper markdown tables | no |
| [`paper`](#legacy-harness) | Regenerate `paper/stability.md` | no |
| [`ci-width`](#legacy-harness) | Wilson CI width vs n | no |
| [`benchmark-report`](#legacy-harness) | Multi-model benchmark report | no |


## Typed platform commands

### platform-run

```
apertus-eval-prep platform-run --config CONFIG [--out OUT] [--set SET] [--no-raw]
```

| Option | Meaning |
|---|---|
| `--config` | Typed platform YAML run spec (required). |
| `--out` | Output root or report path. |
| `--set` | Dotted config override, e.g. `decoding.seed=2`. Repeatable. |
| `--no-raw` | Disable raw output retention. Use when responses may be sensitive. |

```bash
python -m apertus_eval_prep platform-run --config configs/platform_smoke.yaml --out runs/smoke
```

### platform-matrix

```
apertus-eval-prep platform-matrix --config CONFIG [--out OUT] [--set SET] [--no-raw]
```

Expands the declared factors into a deterministic matrix; each cell writes its own
artifacts and records the parent experiment id. The config must contain an `experiment:`
block — pointing it at a plain run spec fails with
`experiment.base: is required (the shared run spec)`.

```bash
python -m apertus_eval_prep platform-matrix --config configs/platform_matrix.yaml --out runs/matrix
```

### platform-compare

```
apertus-eval-prep platform-compare --baseline BASELINE --candidate CANDIDATE --out OUT
```

Refuses to compare runs whose identity (dataset, task, prompt, metric definition) differs.
`BASELINE` and `CANDIDATE` are run **directories**.

### platform-episode

```
apertus-eval-prep platform-episode --config CONFIG [--out OUT] [--set SET] [--no-raw]
```

RAG and agent episode evaluation. The adapter kind selects the mode; the Phase 3 configs
cover both.

```bash
python -m apertus_eval_prep platform-episode --config configs/platform_phase3_rag.yaml   --out runs/rag
python -m apertus_eval_prep platform-episode --config configs/platform_phase3_agent.yaml --out runs/agent
```

### platform-safety

```
apertus-eval-prep platform-safety --config CONFIG [--out OUT] [--set SET] [--no-raw]
```

Runs the sanitized safety suite. Output is a red-team evaluation over the declared taxonomy.

### platform-export-review

```
apertus-eval-prep platform-export-review --run RUN --out OUT
        [--dimensions DIMENSIONS ...] [--sample-size SAMPLE_SIZE]
        [--sampling-strategy {random,stratified,priority}] [--seed SEED]
        [--baseline-run BASELINE_RUN] [--study-id STUDY_ID]
```

Emits a **sanitized** JSONL package for annotators. The output records
`human_reviewed: false`; the package is a request for review, not evidence of it.

### platform-ingest-review

```
apertus-eval-prep platform-ingest-review --input INPUT --out OUT [--study-id STUDY_ID]
```

Validates annotations and writes an agreement summary. An annotation not marked completed
raises `ReviewValidationError: annotation is not completed`, so an unfinished review can
never be reported as agreement. Agreement measures annotator consistency, not correctness
or safety.

### platform-study-analyze

```
apertus-eval-prep platform-study-analyze --study-config STUDY_CONFIG --runs RUNS [RUNS ...]
        [--reviews REVIEWS] --out OUT
```

`RUNS` takes run **directories** (two or more). The command refuses runs belonging to a
different `study_id` and refuses runs missing required artifacts, rather than aggregating
incompatible evidence. Output records `evidence_modes` and `real_model_evidence_available`.

```bash
python -m apertus_eval_prep platform-study-analyze \
    --study-config configs/studies/phase8_mock_study.yaml \
    --runs runs/study_runs/<run_a> runs/study_runs/<run_b> \
    --out reports/study
```

### platform-ingest-runs

```
apertus-eval-prep platform-ingest-runs --runs RUNS [RUNS ...] --out OUT [--allow-incompatible]
```

Converts completed run artifacts into Phase 5 deployment comparison points. `--out` is a
JSON **file** path. Without `--allow-incompatible`, mismatched identities are rejected;
with it, they are recorded as warnings.

```bash
python -m apertus_eval_prep platform-ingest-runs --runs runs/smoke/<run_id> --out points.json
```

### platform-select

```

## Legacy harness

These commands drive the original frozen-prompt research harness. They are tested and
supported, but they write artifacts that predate the evidence-mode system, so their outputs
must not be described as platform evidence.

| Command | Signature |
|---|---|
| `eval` | `--config CONFIG --out OUT [--chat-template {tokenizer,none,mismatched}] [--model-id MODEL_ID] [--limit LIMIT]` |
| `dump-prompts` | `--config CONFIG --out OUT [--backend {hf,vllm}] [--chat-template {tokenizer,none,mismatched}] [--n N]` |
| `compare` | positional `A B --out OUT` — diff two eval JSON files |
| `sweep` | `--config CONFIG --out-dir DIR [--registry REGISTRY] [--profile {t4,a10,cpu}] [--limit LIMIT] [--dry-run] [--force]` |
| `report` | `--registry REGISTRY --out OUT` — Wilson CIs, Kendall tau, plots |
| `experiment` | `--config CONFIG [--registry REGISTRY] [--out OUT] [--n-boot N] [--seed S]` |
| `reproduce` | `[--run-id RUN_ID] [--config-hash HASH] [--check]` — print a replay command |
| `ers` | `--registry REGISTRY [--task TASK] [--n-boot N] [--seed S]` |
| `pareto` | `--run RUN` (repeatable) `--out OUT` — accuracy vs cost |
| `failures` | `--run RUN` (repeatable) `--out OUT` — failure taxonomy |
| `profile` | `--run RUN --out OUT` — runtime/token profile |
| `dashboard` | `--registry REGISTRY [--n-boot N] [--seed S] [--run RUN] [--section NAME]` |
| `site` | `--registry REGISTRY --out OUT [--n-boot N] [--n-perm N] [--seed S]` |
| `catalog` | `--out DIR` — dataset fingerprints and model coverage |
| `paper-tables` | `--registry REGISTRY --out OUT` |
| `paper` | `--registry REGISTRY --out-dir DIR` |
| `ci-width` | `--run NAME=PATH` (repeatable) `--out OUT` |
| `benchmark-report` | `--run NAME=PATH` (repeatable) `--out OUT` |

Examples used by the `Makefile`:

```bash
make smoke            # eval with configs/smoke.yaml
make test             # pytest -q
make report           # research report + paper tables from the registry
make figures          # regenerate paper/ from registry_paper.jsonl
```

## Error behaviour

Config and identity errors are raised as typed exceptions carrying the offending field:

| Situation | Message |
|---|---|
| Matrix config without `experiment:` | `experiment.base: is required (the shared run spec)` |
| Run spec passed to a command expecting an experiment spec | `<path> looks like an experiment spec; use load_experiment_spec() instead` |
| Study run missing required artifacts | `study runs are missing required artifacts` (with the missing names) |
| Study runs from a different study | `study run artifacts are incompatible` (with conflicting fields) |
| Incomplete review annotation | `annotation is not completed` |
| Inconsistent evidence declaration | `<MODE> evidence requires real_model_execution=true` (and similar) |

These messages name the field and the expectation, so a failure is diagnosable without
reading the source.

apertus-eval-prep platform-select --points POINTS [--constraints CONSTRAINTS] [--out OUT]
```

Computes the Pareto frontier and applies constraints. When evidence is insufficient the
result carries `insufficient_evidence: true` rather than a fabricated recommendation.
`CONSTRAINTS` is a JSON file; omit it to get the frontier with status `NO_CONSTRAINTS`.

It is **not** a safety certification, and the gate payload repeats that disclaimer.

```bash
python -m apertus_eval_prep platform-safety --config configs/platform_phase4_safety.yaml --out runs/safety
```

### platform-report

```
apertus-eval-prep platform-report --run RUN [--format {markdown,html,both}] [--out OUT]
                                  [--baseline-run BASELINE_RUN]
```

Rebuilds reports from an immutable run **without re-running a model**. Escapes dynamic
HTML, renders the evidence label, and preserves missing evidence as unavailable rather than
zero. `--format` defaults to `both`; `--out` defaults to the run directory.

### platform-fingerprint

```
apertus-eval-prep platform-fingerprint --run RUN [--baseline-run BASELINE_RUN]
```

Rebuilds the derived `failure_fingerprint.json` from `failures.jsonl`. Priorities are a
triage aid, not causal claims.

### platform-gate

```
apertus-eval-prep platform-gate --run RUN [--rules RULES]
```

`RULES` is a YAML gate policy (see `configs/release_gates/`). A passing gate is a policy aid
evaluated against thresholds this repository defines — **not production approval**.
