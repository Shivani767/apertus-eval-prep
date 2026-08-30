# Apertus Eval Prep

### A Reproducible Framework for Configuration-Sensitive LLM Evaluation

**A reproducible empirical study of how prompts, chat templates, inference backends, quantization, decoding settings, and hardware affect LLM benchmark outcomes and model-ranking stability.**

[![Research Artifact](https://img.shields.io/badge/Status-Research%20Artifact-blue)](https://github.com/Shivani767/apertus-eval-prep)
[![Tests](https://img.shields.io/badge/Tests-58%20passing-success)](https://github.com/Shivani767/apertus-eval-prep/tree/master/tests)
[![License](https://img.shields.io/badge/License-MIT-green)](https://github.com/Shivani767/apertus-eval-prep/blob/master/LICENSE)

---

## Abstract

LLM benchmark scores are often presented as if they were intrinsic properties of a model.

In practice, evaluation outcomes can depend on the **complete measurement configuration**: prompt formulation, few-shot examples, chat templates, inference backends, quantization, decoding parameters, hardware, and runtime environment.

**Apertus Eval Prep** investigates this problem empirically.

The central idea is simple:

> **An evaluation result is not only a property of the model. It is a measurement produced by a model under a specific evaluation configuration.**

The project provides a reproducible research framework for measuring how configuration changes affect:

* benchmark accuracy
* model rankings
* evaluation stability
* inference behavior
* quantization effects
* robustness
* hallucination
* safety
* thinking-mode behavior
* cost

The project is designed as a **research artifact rather than a leaderboard generator**. Experimental configurations, result registries, raw artifacts, generated reports, statistical analysis, and validation documentation are committed so that results can be inspected and reproduced.

---

# Research Question

## Primary Research Question

> **How much do benchmark scores and model rankings change when the evaluation pipeline changes, even when the underlying model and task slice are held fixed?**

The project models evaluation as:

$$
R =
f(M,D,P,T,B,Q,S,H)
$$

where:

* \(M\) = model
* \(D\) = dataset / task slice
* \(P\) = prompt specification
* \(T\) = chat template
* \(B\) = inference backend
* \(Q\) = quantization
* \(S\) = decoding / sampling configuration
* \(H\) = hardware and runtime environment

Therefore, a benchmark result is represented conceptually as:

$$
\text{Model} \times
\text{Task} \times
\text{Configuration}
$$

rather than as a single isolated score.

---

# Research Motivation

Suppose the same model is evaluated under two configurations:

```text
Configuration A
Model + Prompt A + Backend A + FP16
                 ↓
                72%


Configuration B
Model + Prompt B + Backend B + INT8
                 ↓
                68%
```

A conventional benchmark may report:

```text
Model = 72%
```

or:

```text
Model = 68%
```

without making the evaluation conditions prominent.

This project asks:

> **How much of the observed difference comes from the evaluation pipeline itself?**

This matters when:

* comparing LLMs
* reproducing benchmark results
* constructing leaderboards
* evaluating quantized models
* comparing inference systems
* selecting models for downstream applications
* interpreting published benchmark claims

---

# Research Hypotheses

The current experimental design investigates several hypotheses.

### H1 — Prompt Sensitivity

Changing prompt formulation can materially change measured model performance.

### H2 — Configuration Sensitivity

Evaluation details such as chat templates, inference backends, and decoding settings can affect measured outcomes.

### H3 — Ranking Instability

Model rankings can change under different evaluation configurations.

### H4 — Model-Dependent Effects

The same configuration change does not necessarily affect all models equally or in the same direction.

### H5 — Statistical Uncertainty

Observed differences should be interpreted together with uncertainty and statistical evidence rather than relying only on raw point estimates.

---

# Experimental Methodology

The core experimental methodology uses **controlled one-factor-at-a-time (OFAT) experiments**.

A baseline configuration is frozen and one experimental factor is changed while the remaining conditions are held constant.

```text
                         Baseline
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
           Prompt        Backend      Quantization
              │             │             │
              ▼             ▼             ▼
           Result        Result        Result
              │             │             │
              └─────────────┼─────────────┘
                            ▼
                   Statistical Analysis
                            │
                            ▼
                    Ranking Stability
                            │
                            ▼
                     Research Findings
```

This design makes it possible to distinguish between:

* model capability differences
* prompt effects
* formatting/template effects
* backend effects
* quantization effects
* decoding effects
* hardware/runtime effects

---

# Experimental Factors

The research matrix currently includes the following dimensions:

| Factor                  | Purpose                                     |
| ----------------------- | ------------------------------------------- |
| **Model**               | Compare model families / revisions          |
| **Task slice**          | Keep the evaluated task fixed               |
| **Prompt format**       | Measure prompt sensitivity                  |
| **Few-shot examples**   | Measure contextual prompting effects        |
| **Chat template**       | Measure formatting/template effects         |
| **Backend**             | Compare inference implementations           |
| **Quantization**        | Measure lower-precision effects             |
| **Temperature**         | Measure decoding sensitivity                |
| **Seed**                | Control stochasticity                       |
| **Hardware**            | Account for runtime/environment differences |
| **Thinking mode**       | Evaluate reasoning-mode behavior            |
| **Safety tasks**        | Evaluate safety-related behavior            |
| **Hallucination tasks** | Evaluate factual/unsupported generation     |
| **Cost**                | Measure evaluation cost                     |

---

# Research Artifact Philosophy

The project follows one central principle:

> **A result should be replayable, not merely reported.**

Each experimental result is associated with:

* an explicit configuration
* a result registry entry
* experiment metadata
* committed artifacts
* source-code version / git commit
* generated analysis

This makes the provenance of a result inspectable.

The project intentionally avoids silently filling missing measurements or presenting unverified numbers.

---

# Current Verified Status

The current paper-result matrix contains:

### **23 / 34 completed cells**

### **11 cells remaining**

Progress:

$$
\frac{23}{34} \times 100 = \mathbf{67.6\%}
$$

The repository contains the committed paper registry and downloaded result archive.

Primary artifacts:

* [`results/registry_paper.jsonl`](https://github.com/Shivani767/apertus-eval-prep/blob/master/results/registry_paper.jsonl)
* [`results/paper_matrix_partial.zip`](https://github.com/Shivani767/apertus-eval-prep/blob/master/results/paper_matrix_partial.zip)
* [`results/runs/`](https://github.com/Shivani767/apertus-eval-prep/tree/master/results/runs)

> **Research integrity note:** only committed measurements are reported as results. Missing experimental cells remain explicitly incomplete rather than being estimated.

---

# Results

## Experiment 1 — Prompt Sensitivity

The three-model control cohort contains **800 evaluation examples per configuration**.

### Raw Results

| Model       | Control | Concise |  5-shot |
| ----------- | ------: | ------: | ------: |
| **SmolLM2** | 318/800 | 186/800 | 274/800 |
| **Qwen-3B** | 515/800 | 410/800 | 549/800 |
| **Phi-3.5** | 536/800 | 471/800 | 451/800 |

### Accuracy

| Model       |    Control |    Concise |     5-shot |
| ----------- | ---------: | ---------: | ---------: |
| **SmolLM2** | **39.75%** | **23.25%** | **34.25%** |
| **Qwen-3B** | **64.38%** | **51.25%** | **68.63%** |
| **Phi-3.5** | **67.00%** | **58.88%** | **56.38%** |

---

## Prompt Sensitivity — Absolute Changes

Relative to the control configuration:

| Model       |            Concise Δ |            5-shot Δ |
| ----------- | -------------------: | ------------------: |
| **SmolLM2** | −132 (**−16.50 pp**) |  −44 (**−5.50 pp**) |
| **Qwen-3B** | −105 (**−13.13 pp**) |  +34 (**+4.25 pp**) |
| **Phi-3.5** |   −65 (**−8.13 pp**) | −85 (**−10.63 pp**) |

The largest observed prompt effect is:

### **Qwen-3B: 51.25% → 68.63%**

A change of:

### **+17.38 percentage points**

The same prompt change affects Phi-3.5 in the opposite direction:

### **67.00% → 56.38%**

A change of:

### **−10.63 percentage points**

This demonstrates that configuration effects can be **model-dependent**.

---

# Model Ranking Stability

The prompt experiments also demonstrate that model rankings are not necessarily invariant.

### Control

```text
1. Phi-3.5       67.00%
2. Qwen-3B       64.38%
3. SmolLM2       39.75%
```

### Concise

```text
1. Phi-3.5       58.88%
2. Qwen-3B       51.25%
3. SmolLM2       23.25%
```

### 5-shot

```text
1. Qwen-3B       68.63%
2. Phi-3.5       56.38%
3. SmolLM2       34.25%
```

### Key observation

The top-ranked model changes:

```text
Control
Phi-3.5
   ↓
5-shot
Qwen-3B
```

Therefore:

> **A benchmark leaderboard can depend on the evaluation configuration used to produce it.**

This is one of the central empirical observations of the project.

---

# Experiment 2 — Backend Sensitivity

The backend experiment keeps the task slice, model and prompt payload fixed while changing the serving implementation.

### Raw Results

| Model       | HF Generate |    vLLM |
| ----------- | ----------: | ------: |
| **SmolLM2** |     318/800 | 336/800 |
| **Qwen-3B** |     515/800 | 534/800 |
| **Phi-3.5** |     536/800 | 537/800 |

### Accuracy

| Model       | HF Generate |       vLLM |   Difference |
| ----------- | ----------: | ---------: | -----------: |
| **SmolLM2** |  **39.75%** | **42.00%** | **+2.25 pp** |
| **Qwen-3B** |  **64.38%** | **66.75%** | **+2.38 pp** |
| **Phi-3.5** |  **67.00%** | **67.13%** | **+0.13 pp** |

### Interpretation

The largest observed backend difference is:

**Qwen-3B: +2.38 percentage points**

while Phi-3.5 changes by only:

**+0.13 percentage points**

This suggests that backend effects can be observable while also being **model-dependent**.

The result does not establish that one backend is universally superior.

Instead:

> **Inference backend should be treated as part of the experimental configuration.**

---

# Experiment 3 — Quantization

The project includes quantization experiments comparing lower-precision configurations against matched controls.

For the committed Qwen-3B measurements:

| Configuration | Correct |   Accuracy |
| ------------- | ------: | ---------: |
| **INT8**      | 518/800 | **64.75%** |
| **INT4**      | 525/800 | **65.63%** |

Difference:

### **+7 examples / +0.88 percentage points**

for INT4 relative to INT8 in this specific experiment.

This result should **not** be interpreted as evidence that INT4 is universally better than INT8.

The scientifically appropriate conclusion is:

> **Quantization effects are configuration- and model-dependent and require matched experiments across models, tasks, hardware and backends before broader conclusions can be drawn.**

---

# Experiment 4 — Thinking, Robustness, Safety, Hallucination and Cost

The benchmark suite has been extended beyond the original frozen evaluation canary.

The current framework includes experimental infrastructure for:

### Thinking

Controlled evaluation of thinking/reasoning-mode configurations.

### Robustness

Evaluation of model behavior under robustness-oriented task variations.

### Hallucination

Measurement and reporting of hallucination-related behavior.

### Safety

Dedicated safety-oriented benchmark tasks.

### Cost

Tracking evaluation cost alongside benchmark outcomes.

These additions allow the framework to move beyond a single scalar accuracy score and study **quality, robustness and efficiency jointly**.

---

# Results Summary

The current committed measurements can be summarized as follows:

| Research factor             | Observed result       |
| --------------------------- | --------------------- |
| **Qwen-3B prompt range**    | 51.25% → 68.63%       |
| **Qwen-3B prompt effect**   | **17.38 pp**          |
| **Phi-3.5 prompt range**    | 56.38% → 67.00%       |
| **SmolLM2 prompt range**    | 23.25% → 39.75%       |
| **Largest backend effect**  | **Qwen-3B: +2.38 pp** |
| **SmolLM2 backend effect**  | +2.25 pp              |
| **Phi-3.5 backend effect**  | +0.13 pp              |
| **Qwen INT8**               | 64.75%                |
| **Qwen INT4**               | 65.63%                |
| **Quantization difference** | +0.88 pp              |
| **Paper matrix**            | 23 / 34 cells         |
| **Completion**              | 67.6%                 |
| **Automated tests**         | 58 passing            |

---

# Main Findings

## Finding 1 — Prompt configuration materially affects measured performance

The largest observed prompt difference is:

**Qwen-3B: 51.25% → 68.63%**

which corresponds to:

**+17.38 percentage points**

---

## Finding 2 — Model rankings can change

The control configuration ranks:

**Phi-3.5 > Qwen-3B > SmolLM2**

while the 5-shot configuration ranks:

**Qwen-3B > Phi-3.5 > SmolLM2**

Thus, evaluation configuration can affect not only absolute scores but also conclusions about which model performs best.

---

## Finding 3 — Backend choice can affect evaluation results

The current backend experiment produces changes of:

* SmolLM2: **+2.25 pp**
* Qwen-3B: **+2.38 pp**
* Phi-3.5: **+0.13 pp**

The magnitude differs substantially by model.

---

## Finding 4 — Quantization effects should not be generalized from one experiment

The current Qwen-3B measurements show:

**INT8 = 64.75%**

**INT4 = 65.63%**

A difference of only:

**0.88 percentage points**

This illustrates why quantization claims require matched experiments across multiple conditions.

---

## Finding 5 — Missing data should remain missing

The current matrix is:

**23 / 34 completed**

rather than artificially presenting a complete leaderboard.

The remaining 11 cells are explicitly tracked.

This is intentional.

> **The project prioritizes measurement integrity over artificial completeness.**

---

# Statistical Methodology

The project incorporates statistical analysis so that raw score differences are not automatically interpreted as meaningful capability differences.

## Confidence Intervals

Performance estimates can be accompanied by confidence intervals to represent measurement uncertainty.

---

## Paired Statistical Testing

Models evaluated on the same examples produce paired observations.

The project includes **McNemar's test** where appropriate for comparing paired binary predictions.

This allows the analysis to ask:

> Is the observed difference supported by the paired prediction outcomes?

rather than relying only on:

```text
Model A = 72%
Model B = 69%
```

---

## Ranking Stability

The project uses rank-correlation analysis, including **Kendall's τ**, to compare model rankings across configurations.

Conceptually:

$$
\tau =
\text{agreement between two model rankings}
$$

This allows ranking changes to be quantified rather than interpreted only visually.

---

## Derived Metrics

The analysis framework also includes derived metrics for:

* thinking-mode comparisons
* quantization analysis
* ranking stability
* Pareto analysis
* cost-aware evaluation
* multi-model comparison

---

# Reproducibility

Reproducibility is a core research requirement.

The intended workflow is:

```text
Experiment Configuration
          ↓
       Evaluation
          ↓
     Raw Results
          ↓
    Result Registry
          ↓
 Statistical Analysis
          ↓
 Tables / Figures
          ↓
 Research Report
```

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
58 tests passing
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

---

# Reproduction and Provenance

The project provides a reproduction CLI and configuration-driven workflow.

The goal is to make it possible to trace:

```text
Published Finding
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

This makes the relationship between **research claim and experimental evidence** inspectable.

---

# Validation

The repository contains dedicated research documentation covering implementation, methodology and validation.

### Implementation Audit

[`docs/IMPLEMENTATION_AUDIT.md`](https://github.com/Shivani767/apertus-eval-prep/blob/master/docs/IMPLEMENTATION_AUDIT.md)

Documents the relationship between the research methodology and implementation.

### Statistical Methodology

[`docs/STATISTICAL_METHODOLOGY.md`](https://github.com/Shivani767/apertus-eval-prep/blob/master/docs/STATISTICAL_METHODOLOGY.md)

Documents the statistical methods used by the project.

### Validation

[`docs/VALIDATION.md`](https://github.com/Shivani767/apertus-eval-prep/blob/master/docs/VALIDATION.md)

Documents validation of the committed research artifacts.

### Related Work

[`paper/RELATED_WORK.md`](https://github.com/Shivani767/apertus-eval-prep/blob/master/paper/RELATED_WORK.md)

Places the research within the relevant literature.

---

# Research Outputs

The repository contains the research write-up and generated artifacts.

### Paper Status

[`paper/run_status.md`](https://github.com/Shivani767/apertus-eval-prep/blob/master/paper/run_status.md)

Tracks the current experimental matrix.

### Generated Tables

[`paper/_generated_tables.md`](https://github.com/Shivani767/apertus-eval-prep/blob/master/paper/_generated_tables.md)

Contains tables generated from the committed research data.

### Stability Analysis

[`reports/stability_paper/stability.md`](https://github.com/Shivani767/apertus-eval-prep/blob/master/reports/stability_paper/stability.md)

Contains model-ranking stability analysis.

### Research Registry

[`results/registry_paper.jsonl`](https://github.com/Shivani767/apertus-eval-prep/blob/master/results/registry_paper.jsonl)

The committed experimental result registry.

---

# Threats to Validity

The conclusions of this study are bounded by the models, datasets, hardware and configurations that have actually been evaluated.

## Internal Validity

Observed differences may arise from implementation or runtime factors that are not completely controlled.

The project reduces this risk through frozen configurations, controlled experiments and explicit metadata.

## External Validity

Results obtained from a particular set of models and task slices should not automatically be generalized to all LLMs or benchmarks.

## Construct Validity

Accuracy is only one measure of model behavior.

The project therefore extends the evaluation suite to additional dimensions such as:

* robustness
* hallucination
* safety
* thinking behavior
* cost

## Reproducibility

LLM evaluation may depend on:

* model revision
* software version
* inference backend
* hardware
* random seed
* decoding parameters

These variables are therefore treated as part of the evaluation environment.

---

# Limitations

This project is **not intended to produce a universal LLM leaderboard**.

The current paper matrix is incomplete:

**23 / 34 cells completed**

and the remaining cells are explicitly tracked.

The current conclusions are therefore:

* empirical
* configuration-specific
* bounded by the available measurements
* subject to the limitations of the evaluated models and datasets

The project intentionally distinguishes between:

```text
Measured
   ↓
Derived
   ↓
Unverified / Missing
```

rather than presenting incomplete evidence as a complete result.

---

# Why Configuration-Aware Evaluation Matters

A conventional benchmark may produce:

```text
Model A = 68%
Model B = 64%
```

This project asks:

```text
68% under which configuration?

64% under which configuration?

Would the ranking remain unchanged
under another valid evaluation setup?
```

The current experiments demonstrate that this question is not theoretical.

For the evaluated cohort:

* Qwen-3B changes from **51.25% to 68.63%** across tested prompt configurations.
* Phi-3.5 changes from **56.38% to 67.00%**.
* SmolLM2 changes from **23.25% to 39.75%**.
* Qwen-3B changes by **2.38 percentage points** between the tested HF and vLLM configurations.

Therefore:

> **Benchmark results should be interpreted together with the configuration that produced them.**

---

# Relation to AI for Software Engineering

The current project focuses on LLM evaluation methodology, but the framework naturally extends to **AI for Software Engineering (AI4SE)**.

The same methodology can be applied to:

* code understanding
* code generation
* code translation
* bug detection
* code repair
* repository-level reasoning
* static-analysis assistance

For example, a future experiment could investigate:

> **How stable are LLM rankings on software-engineering tasks when prompt format, repository context, inference backend and decoding configuration change?**

This connects the methodology to research at the intersection of:

**AI × Software Engineering × Programming Languages**

and provides a foundation for studying reliable evaluation of AI systems operating on real-world codebases.

---

# Future Research

Planned and possible extensions include:

### Experimental

* Complete the remaining paper-matrix cells
* Increase model coverage
* Increase task coverage
* Expand quantization experiments
* Evaluate additional inference backends
* Study temperature and sampling sensitivity
* Expand robustness experiments

### Statistical

* Multi-factor experimental designs
* Interaction-effect analysis
* Multiple-comparison correction
* Larger-scale ranking stability analysis
* Effect-size reporting
* Bootstrap-based uncertainty analysis

### AI for Software Engineering

* Code-generation benchmarks
* Code-repair evaluation
* Code-translation experiments
* Static-analysis-assisted evaluation
* Repository-level reasoning
* Large-codebase evaluation
* Agentic software-engineering tasks

### Systems

* Quality / latency / memory trade-offs
* Quality / cost trade-offs
* Hardware-aware evaluation
* Reproducible inference environments

---

# Repository Structure

```text
apertus-eval-prep/
│
├── configs/
│   └── Experiment configurations
│
├── data/
│   └── Evaluation data and task artifacts
│
├── docs/
│   ├── IMPLEMENTATION_AUDIT.md
│   ├── STATISTICAL_METHODOLOGY.md
│   └── VALIDATION.md
│
├── notebooks/
│   └── Research / experiment notebooks
│
├── paper/
│   ├── RELATED_WORK.md
│   ├── run_status.md
│   └── _generated_tables.md
│
├── reports/
│   └── Generated research reports
│
├── results/
│   ├── registry_paper.jsonl
│   ├── paper_matrix_partial.zip
│   └── runs/
│
├── scripts/
│   └── Experiment and reporting utilities
│
├── src/
│   └── apertus_eval_prep/
│       └── Core implementation
│
├── tests/
│   └── Automated tests
│
├── CITATION.cff
├── Dockerfile
├── LICENSE
├── Makefile
├── pyproject.toml
└── README.md
```

---

# Current Research Status

| Metric                   |            Status |
| ------------------------ | ----------------: |
| Paper matrix             | **23 / 34 cells** |
| Completion               |         **67.6%** |
| Remaining cells          |            **11** |
| Automated tests          |    **58 passing** |
| Statistical methodology  |   **Implemented** |
| Reproduction CLI         |     **Available** |
| Result registry          |     **Committed** |
| Paper artifacts          |     **Committed** |
| Validation documentation |     **Available** |
| Benchmark suite          |      **Extended** |

---

# Research Contribution

The project contributes a reproducible framework for studying an often-overlooked question in LLM evaluation:

> **How much confidence should we place in a benchmark conclusion when the evaluation configuration itself can change the measured result?**

The current work demonstrates empirically that:

1. Prompt configuration can substantially change model performance.
2. Model rankings can change across prompt configurations.
3. Inference backend can produce measurable differences.
4. Quantization effects should be evaluated experimentally rather than assumed.
5. Statistical uncertainty should accompany model comparisons.
6. Evaluation configuration should be treated as part of the measurement.
7. Missing experimental evidence should remain explicitly missing.

---

# Citation

If you use the framework, methodology, or research artifacts, please cite:

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

## Research Status

**Active research artifact — results are added as experiments are completed.**

The repository deliberately separates **measured results, derived analysis, and pending experiments** to preserve research integrity and reproducibility.
