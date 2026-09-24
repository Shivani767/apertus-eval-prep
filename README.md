# Apertus Eval Prep

### A reproducible LLM evaluation system for measuring how models, prompts, inference backends, quantization, decoding, and runtime configuration affect benchmark results.

[![Research Artifact](https://img.shields.io/badge/Status-Research%20Artifact-blue)](https://github.com/Shivani767/apertus-eval-prep)
[![Tests](https://img.shields.io/badge/Tests-135%20passing-success)](https://github.com/Shivani767/apertus-eval-prep/tree/master/tests)
[![License](https://img.shields.io/badge/License-MIT-green)](https://github.com/Shivani767/apertus-eval-prep/blob/master/LICENSE)

---

## What I Built

**Apertus Eval Prep is a configuration-driven LLM evaluation framework.**

Instead of treating a benchmark score as just:

```text
Model → Score
```

the system records the conditions that produced the score:

```text
Model
  +
Task
  +
Prompt
  +
Chat Template
  +
Backend
  +
Quantization
  +
Decoding
  +
Hardware / Runtime
      ↓
  Evaluation
      ↓
  Result Registry
      ↓
  Statistical Analysis
      ↓
  Reports / Findings
```

This makes experiments **repeatable, comparable, and inspectable**.

The framework is designed for situations where you need to answer practical questions such as:

* Did changing the prompt actually improve the model?
* Does the result survive a different inference backend?
* Does quantization change benchmark behavior?
* Does the model ranking stay the same?
* How much variation comes from the evaluation setup itself?
* Can another researcher reproduce the reported number?

---

# Why This Matters

LLM benchmark numbers are often presented as if they were intrinsic properties of a model.

In practice, the measured result can also depend on the evaluation pipeline.

For example, in the current experiments:

```text
Qwen-3B

Concise prompt
      ↓
   51.25%

5-shot prompt
      ↓
   68.63%
```

That's a:

**+17.38 percentage-point difference**

without changing the underlying model.

For another model, the same type of prompt change moved performance in the opposite direction:

```text
Phi-3.5

5-shot
  ↓
56.38%

Control
  ↓
67.00%
```

The result is therefore not simply:

```text
Model = Score
```

It is better represented as:

```text
Model × Task × Evaluation Configuration = Measured Result
```

Apertus Eval Prep makes that configuration explicit and reproducible.

---

# How It Works

The framework follows a simple pipeline.

```text
┌──────────────────────┐
│ Experiment Config    │
│ YAML / parameters    │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│ Evaluation Runner    │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│ Model / Backend      │
│ HF / vLLM / etc.     │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│ Task Evaluation      │
│ predictions / scores │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│ Result Registry      │
│ config + result      │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│ Statistical Analysis │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│ Tables / Reports     │
└──────────────────────┘
```

Every experiment is driven by configuration rather than hard-coded evaluation logic.

A result can therefore be traced from:

```text
Finding
  ↓
Generated Report
  ↓
Result Registry
  ↓
Experiment Configuration
  ↓
Source Code
  ↓
Git Commit
```

---

# What the System Tracks

The evaluation configuration can include:

| Dimension             | Purpose                                |
| --------------------- | -------------------------------------- |
| **Model**             | Compare model families and revisions   |
| **Task slice**        | Keep the evaluated workload controlled |
| **Prompt**            | Measure prompt sensitivity             |
| **Few-shot examples** | Measure contextual prompting effects   |
| **Chat template**     | Measure formatting effects             |
| **Backend**           | Compare inference implementations      |
| **Quantization**      | Measure lower-precision effects        |
| **Temperature**       | Measure decoding sensitivity           |
| **Seed**              | Control stochastic variation           |
| **Hardware**          | Track runtime environment              |
| **Thinking mode**     | Compare reasoning configurations       |
| **Safety**            | Evaluate safety-oriented behavior      |
| **Hallucination**     | Evaluate unsupported generation        |
| **Cost**              | Track evaluation cost                  |

The important engineering decision is that these are treated as **first-class experiment metadata**, rather than being hidden inside scripts.

---

# Results

The current committed experiments already show that evaluation configuration can materially affect measured outcomes.

## Prompt Sensitivity

The three-model control cohort contains **800 evaluation examples per configuration**.

| Model       | Control | Concise |     5-shot |
| ----------- | ------: | ------: | ---------: |
| **SmolLM2** |  39.75% |  23.25% |     34.25% |
| **Qwen-3B** |  64.38% |  51.25% | **68.63%** |
| **Phi-3.5** |  67.00% |  58.88% |     56.38% |

### Largest observed prompt effect

**Qwen-3B: 51.25% → 68.63%**

**+17.38 percentage points**

The effect is model-dependent:

* SmolLM2: −5.50 pp for 5-shot vs control
* Qwen-3B: **+4.25 pp**
* Phi-3.5: −10.63 pp

The broader range across tested prompt configurations is even larger:

```text
Qwen-3B
51.25% ─────────────────────── 68.63%
              +17.38 pp
```

---

# Model Ranking Can Change

Under the control configuration:

```text
1. Phi-3.5       67.00%
2. Qwen-3B       64.38%
3. SmolLM2       39.75%
```

Under 5-shot prompting:

```text
1. Qwen-3B       68.63%
2. Phi-3.5       56.38%
3. SmolLM2       34.25%
```

The top-ranked model changes.

This is one of the most important findings from the current experiments:

> **The conclusion about which model performs best can depend on the evaluation configuration.**

---

# Backend Sensitivity

The backend experiment keeps the model, task slice, and prompt payload fixed while changing the inference implementation.

| Model       | Hugging Face |   vLLM |   Difference |
| ----------- | -----------: | -----: | -----------: |
| **SmolLM2** |       39.75% | 42.00% |     +2.25 pp |
| **Qwen-3B** |       64.38% | 66.75% | **+2.38 pp** |
| **Phi-3.5** |       67.00% | 67.13% |     +0.13 pp |

The effect is measurable but not uniform.

The largest observed difference is:

**Qwen-3B: +2.38 percentage points**

The correct conclusion is not that one backend is universally better.

Instead:

> **The inference backend is part of the evaluation configuration and should be recorded when comparing results.**

---

# Quantization

The framework also evaluates lower-precision configurations against matched controls.

For the committed Qwen-3B measurements:

| Configuration |   Correct | Accuracy |
| ------------- | --------: | -------: |
| **INT8**      | 518 / 800 |   64.75% |
| **INT4**      | 525 / 800 |   65.63% |

Difference:

**+7 examples / +0.88 percentage points**

For the committed Phi-3.5 measurements:

| Configuration |   Correct | Accuracy |
| ------------- | --------: | -------: |
| **Control**   | 536 / 800 |   67.00% |
| **INT8**      | 538 / 800 |   67.25% |
| **INT4**      | 559 / 800 |   69.88% |

Difference vs control:

**INT8: +2 examples / +0.25 pp · INT4: +23 examples / +2.88 pp**

These are results from matched experiments, not evidence that one precision is universally better. The framework is designed to make these comparisons reproducible across additional models, tasks, hardware, and backends.

---

# Sampling Stability

The repository also records repeated runs under controlled sampling settings (T=0.7, top_p=0.95).

For SmolLM2 at temperature 0.7, three seeds produced:

```text
Seed 0 → 36.25% (290/800)
Seed 1 → 37.63% (301/800)
Seed 2 → 39.00% (312/800)
```

For Qwen-3B at temperature 0.7, three seeds produced:

```text
Seed 0 → 64.25% (514/800)
Seed 1 → 65.00% (520/800)
Seed 2 → 63.00% (504/800)
```

This makes stochastic variation visible instead of hiding it behind a single run.

---

# Beyond Accuracy

The framework has been extended beyond a single benchmark score.

Current evaluation infrastructure covers:

### Thinking

Controlled comparison of thinking/reasoning-mode configurations.

### Robustness

Evaluation under robustness-oriented task variations.

### Hallucination

Measurement and reporting of hallucination-related behavior.

### Safety

Dedicated safety-oriented evaluation tasks.

### Cost

Tracking evaluation cost alongside quality metrics.

The goal is to make model evaluation useful for real engineering decisions where:

```text
Quality
+
Reliability
+
Latency
+
Cost
+
Memory
```

may matter more than a single leaderboard score.

---

# Experiment Design

The core paper experiments use **controlled one-factor-at-a-time (OFAT)** comparisons.

A baseline configuration is frozen and one factor is changed while the remaining conditions are kept constant.

```text
                    Baseline
                       │
       ┌───────────────┼───────────────┐
       ↓               ↓               ↓
    Prompt          Backend       Quantization
       │               │               │
       ↓               ↓               ↓
    Result          Result          Result
       └───────────────┼───────────────┘
                       ↓
              Statistical Analysis
                       ↓
                Ranking Stability
```

This allows the framework to separate effects caused by:

* prompt formulation
* few-shot examples
* chat templates
* inference backends
* quantization
* decoding
* hardware/runtime configuration

The design can later be extended to multi-factor experiments when interactions between variables need to be studied.

---

# Statistical Analysis

Raw accuracy differences are not automatically treated as meaningful capability differences.

The analysis layer includes:

### Confidence Intervals

Performance estimates can be accompanied by uncertainty intervals.

### Paired Testing

For paired binary predictions, the project supports **McNemar's test** where appropriate, plus a paired bootstrap CI for the accuracy difference (`bootstrap_paired_diff_ci`, joint per-item resampling) and a sign-flip permutation test (`permutation_paired_test`). When several comparisons are tested at once, Holm–Bonferroni (FWER) and Benjamini–Hochberg (FDR) corrections are available (`holm_bonferroni`, `benjamini_hochberg`). All are Monte-Carlo with fixed seeds and tested on synthetic data.

### Evaluation Reliability Score (provisional)

`evaluation_reliability_score` (in `reliability.py`) summarizes "how much can we trust this ranking" as a weighted mean of four [0,1] components: CI separation (non-overlapping Wilson pairs), bootstrap Kendall-tau, config stability, and seed stability. Components that cannot be computed are reported as `None` and excluded (weights renormalize — nothing imputed). The weights are **provisional**; `ers_ablation()` shows how the score reacts to dropping each component. The current committed 3-model matrix scores **ERS ≈ 0.716** (DERIVED, n=28 usable cells, 3 skipped) — a descriptive summary, not a validated measurement.

### Failure Taxonomy

`failures.py` classifies every scored item into mutually exclusive categories: `runtime_error`, `empty_output`, `unparseable`, `wrong_answer`, `correct`. Zeros are measured zeros. Real committed counts: Phi-3.5 int4 (69.9% correct) and SmolLM2 HF control (39.8% correct) are broken down per task in `reports/failures/`.

### Runtime Profiling

`profile.py` derives per-task and per-language latency/throughput (tok/s, e2e ms, TTFT, token counts) from measured per-item records. The committed vLLM run records `e2e_ms: 0.0` placeholders — these are counted (`n_e2e_zero_placeholder`) and excluded, never rendered as "0 ms". Committed profiles: Qwen-3B HF control (tok/s mean 10.8, TTFT ≈ 340–650 ms by task) and the vLLM cell (timings unavailable, accuracies still valid).

### Research Dashboard

`python -m apertus_eval_prep dashboard` aggregates registry coverage (MEASURED/SAMPLED/PENDING), the ERS, per-row artifact verification (recomputes config_hash from manifest settings and accuracy from items; currently 31/31 rows verify after a documented correction of 2 stale SmolLM2 sampled rows), and failure taxonomy. Output: `reports/dashboard/`.

### Web Dashboard (frontend/) — live at https://shivani767.github.io/apertus-eval-prep/

A research-grade interactive site (React + Vite + TypeScript + recharts) built around one
question: *"How robust are conclusions about relative LLM capability to reasonable changes
in evaluation configuration?"* Twelve sections: Overview, The Finding (control-vs-variant
ranking reversals), Experiment Explorer (URL-shareable filters), Experiment Detail,
Ranking Stability (bump chart), Results Matrix, Statistical Evidence (bootstrap CI,
permutation, McNemar, Holm/BH), Reliability (provisional ERS + ablation), Failures,
Cost/Pareto, Sampling, Reproducibility (verification + copyable replay commands),
Methodology & Limitations.

Single source of truth — no second dataset:

```bash
python -m apertus_eval_prep site --registry results/registry_paper.jsonl --out reports/site
cd frontend && npm install && npm run copy-data && npm run build   # or: npm run dev
```

`site.py` deterministically exports one `reports/site/site.json` from the committed
registry + run artifacts (cells, rankings, paired statistics, ERS, failures, Pareto,
reproduction checks). `copy-data` copies it to `public/data/site/` (deployed build) and
`src/data/` (vitest fixture). The UI renders PENDING/unavailable as "Not measured",
never 0. Deploys via `.github/workflows/deploy.yml` (generate → test → build → Pages).

### Ranking Stability

**Kendall's τ** is used for comparing model rankings across configurations.

### Derived Analysis

The framework also supports analysis for:

* thinking-mode comparisons
* quantization
* ranking stability
* Pareto analysis
* cost-aware evaluation
* multi-model comparison

---

# Results Are First-Class Artifacts

A major design choice is that experimental results are stored as structured artifacts.

A result contains information such as:

```json
{
  "model": "Qwen2.5-3B-Instruct",
  "prompt": "five_shot",
  "backend": "huggingface",
  "accuracy": 0.6863
}
```

The actual registry contains additional metadata needed to reproduce and audit the experiment.

The repository therefore separates:

```text
Configuration
      ↓
Measurement
      ↓
Registry
      ↓
Derived Analysis
      ↓
Report
```

Missing measurements are not silently estimated or filled in.

---

# Current Research Status

The paper experiment matrix currently tracks:

| Metric                   | Status            |
| ------------------------ | ----------------- |
| Paper matrix             | **31 / 34 cells** |
| Completion               | **91.2%**         |
| Remaining cells          | **3 (Phi `sampled` T=0.7 × 3)** |
| Automated tests          | **231 passing**   |
| Statistical methodology  | **Implemented**   |
| Reproduction CLI         | **Available**     |
| Result registry          | **Committed**     |
| Paper artifacts          | **Committed**     |
| Validation documentation | **Available**     |
| Benchmark suite          | **Extended**      |
| T4 factorial plan        | **Documented** ([`docs/t4_experiment_plan.md`](docs/t4_experiment_plan.md)) |
| T4 runner + offline analyzer | **Implemented** (`scripts/run_t4_research.py`, `scripts/analyze_research_results.py`) |
| Real-model T4 experiments | **Pending — researcher launches Colab/T4 manually** |

> **Only committed measurements are reported as results. Pending cells remain explicitly incomplete.**
>
> **T4 phase status: infrastructure validated; synthetic pipeline validated
> (clearly labeled `synthetic`, never used as evidence); real-model
> experiments pending.** The staged plan, exact commands, and statistical
> discipline for the real runs are in [`docs/t4_experiment_plan.md`](docs/t4_experiment_plan.md).

Primary artifacts:

* [`results/registry_paper.jsonl`](results/registry_paper.jsonl)
* [`results/paper_matrix_partial.zip`](results/paper_matrix_partial.zip)
* [`results/runs/`](results/runs)

---

# Reproducibility

The repository is designed so another developer can clone the project, run the tests, execute an evaluation, and inspect the generated artifacts.

## Setup

```bash
git clone https://github.com/Shivani767/apertus-eval-prep.git
cd apertus-eval-prep

python3 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
```

## Run Tests

```bash
pytest -q
```

Current validation:

```text
231 tests passing
```

## Run a Smoke Evaluation

```bash
python -m apertus_eval_prep eval \
    --config configs/smoke.yaml \
    --out results/smoke.json
```

## Regenerate Research Artifacts

```bash
make paper
make figures
```

## Analysis & Reporting Commands

All analysis commands work on committed artifacts only — nothing is
re-measured, and missing data is reported rather than filled:

```bash
# Aggregate dashboard: coverage, ERS, per-row artifact verification, failures
python -m apertus_eval_prep dashboard

# Failure taxonomy over one or more scored runs (path=label, repeatable)
python -m apertus_eval_prep failures --run results/runs/<run>.json=<label>

# Runtime profile: per-task / per-language tok-s, e2e, TTFT from a scored run
python -m apertus_eval_prep profile --run results/runs/<run>.json

# Quality/latency Pareto front across scored runs
python -m apertus_eval_prep pareto --run results/runs/<run>.json=<label>

# Evaluation Reliability Score for a model x config matrix
python -m apertus_eval_prep ers --registry results/registry_paper.jsonl

# ArtifactCatalog: fingerprinted index of run JSON (sha256, size, model, factor, status, n_items, accuracy, git_commit)
python -m apertus_eval_prep catalog --runs-dir results/runs

# Replay command for a registry row (+ --check verifies the artifact
# against the row: hash recomputation, accuracy, git SHA)
python -m apertus_eval_prep reproduce --run-id <run_id> --check
```

---

# Repository Structure

```text
apertus-eval-prep/
│
├── configs/                 # Experiment configurations
├── data/                    # Evaluation data and task artifacts
│
├── docs/
│   ├── IMPLEMENTATION_AUDIT.md
│   ├── RESEARCH_AUDIT.md
│   ├── RESEARCH_PLAN.md
│   ├── CURRENT_STATE.md
│   ├── ARCHITECTURE.md
│   ├── STATISTICAL_METHODOLOGY.md
│   ├── STATISTICAL_METHODOLOGY_APPENDIX.md
│   ├── METAMORPHIC_EVAL.md
│   ├── EVALUATION_COST.md
│   └── VALIDATION.md
│
├── notebooks/               # Research / experiment notebooks
│
├── notes/                   # Working research notes
│
├── paper/
│   ├── RELATED_WORK.md
│   ├── run_status.md
│   └── _generated_tables.md
│
├── reports/                 # Generated research reports
│
├── results/
│   ├── registry_paper.jsonl
│   ├── paper_matrix_partial.zip
│   └── runs/
│
├── scripts/                 # Experiment / reporting utilities
│
├── src/
│   └── apertus_eval_prep/   # Core implementation
│       ├── cli.py           # Command-line interface
│       ├── config.py        # Configuration loading
│       ├── run_eval.py      # Evaluation runner
│       ├── sweep.py         # Experiment sweep (OFAT + factorial)
│       ├── registry.py      # Result registry
│       ├── catalog.py       # ArtifactCatalog (fingerprinted index)
│       ├── stats.py         # Statistical engine (bootstrap, permutation, MC corrections)
│       ├── stability.py     # Evaluation stability metrics
│       ├── ranking.py       # Ranking robustness
│       ├── reliability.py   # Evaluation Reliability Score (ERS)
│       ├── fragility.py     # Evaluation fragility components
│       ├── variance.py      # Variance decomposition
│       ├── adaptive.py      # Adaptive evaluation engine
│       ├── cost.py          # Evaluation cost tracking
│       ├── failures.py      # Failure taxonomy
│       ├── profile.py       # Runtime profiling
│       ├── pareto.py        # Pareto analysis
│       ├── dashboard.py     # Research dashboard
│       ├── reproduce.py     # Reproduction + verification
│       ├── metamorphic.py   # Metamorphic eval transforms
│       ├── report.py        # Report generation
│       └── ...
│
├── tests/                   # Automated tests (231 passing)
│
├── CITATION.cff
├── Dockerfile
├── LICENSE
├── Makefile
├── pyproject.toml
└── README.md
```

---

# Validation & Research Documentation

The repository includes deeper documentation for readers who want to inspect the methodology and implementation.

* [`docs/IMPLEMENTATION_AUDIT.md`](docs/IMPLEMENTATION_AUDIT.md) — implementation audit
* [`docs/STATISTICAL_METHODOLOGY.md`](docs/STATISTICAL_METHODOLOGY.md) — statistical methods
* [`docs/VALIDATION.md`](docs/VALIDATION.md) — validation of research artifacts
* [`paper/RELATED_WORK.md`](paper/RELATED_WORK.md) — related research
* [`paper/run_status.md`](paper/run_status.md) — experiment matrix status
* [`paper/_generated_tables.md`](paper/_generated_tables.md) — generated research tables
* [`reports/stability_paper/stability.md`](reports/stability_paper/stability.md) — ranking stability analysis

---

# Research Integrity

This project intentionally distinguishes between:

```text
Measured
   ↓
Derived
   ↓
Pending / Missing
```

A result is not presented as complete simply because a number could be estimated.

Each committed measurement should be traceable to its:

* configuration
* task
* model
* runtime
* result
* analysis
* source-code version

This makes the repository useful as both **software and a research artifact**.

---

# Limitations

The current findings are bounded by the models, datasets, hardware, and configurations that have actually been measured.

The project is **not a universal LLM leaderboard**.

Current results should therefore be interpreted as:

* empirical
* configuration-specific
* dependent on the evaluated models and tasks
* limited by the current experiment matrix

The framework is designed to make those boundaries visible rather than hide them.

---

# Where This Goes Next

The same infrastructure can be extended to larger and more practical AI workloads.

### More LLM Evaluation

* More model families
* More task types
* Larger evaluation sets
* Additional inference backends
* More quantization configurations
* Larger sampling studies

### AI for Software Engineering

The evaluation methodology naturally extends to:

* code generation
* code repair
* code translation
* bug detection
* repository-level reasoning
* static-analysis-assisted evaluation
* agentic software-engineering tasks

For example:

```text
Repository
    ↓
Code / Documentation Retrieval
    ↓
LLM / Agent
    ↓
Generated Answer or Patch
    ↓
Tests / Validation
    ↓
Evaluation
```

This creates a direct path from controlled LLM evaluation to evaluating AI systems operating on real software repositories.

### Systems

Future experiments can jointly measure:

```text
Quality
Latency
Memory
Throughput
Cost
```

to study practical quality/efficiency trade-offs.

---

# Why I Built It This Way

The central engineering principle is simple:

> **A benchmark result should be reproducible evidence, not just a number in a table.**

Apertus Eval Prep turns that principle into software:

```text
Configure
   ↓
Run
   ↓
Measure
   ↓
Register
   ↓
Analyze
   ↓
Compare
   ↓
Report
```

The current experiments show why this matters:

**Qwen-3B:** 51.25% → 68.63% across tested prompt configurations

**Qwen-3B:** +2.38 pp between the tested HF and vLLM configurations

**Phi-3.5:** 67.00% → 56.38% under the tested prompt configurations

These are not claims about every model or every benchmark.

They are measured examples showing that **the evaluation pipeline itself can influence what we conclude from an LLM benchmark.**

---

# Citation

If you use the framework, methodology, or research artifacts:

```bibtex
@software{bhandari_apertus_eval,
  author = {Bhandari, Shivani},
  title = {Apertus Eval Prep: A Reproducible Framework for Configuration-Sensitive LLM Evaluation},
  year = {2026},
  url = {https://github.com/Shivani767/apertus-eval-prep}
}
```

---

# Author

**Shivani Bhandari**

AI/ML Research · LLM Evaluation · ML Systems · Software Engineering

GitHub: [Shivani767](https://github.com/Shivani767)

---

### Research Status

**Active research artifact — experiments and results are added as measurements are completed.**
