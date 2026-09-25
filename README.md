# Apertus Eval Prep

### Reliable, configuration-aware evaluation for LLM systems

> **How much of an LLM benchmark result comes from the model — and how much comes from the way we evaluate it?**

[![Research Artifact](https://img.shields.io/badge/Status-Research%20Artifact-blue)](https://github.com/Shivani767/apertus-eval-prep)
[![Tests](https://img.shields.io/badge/Tests-124%20passing-success)](https://github.com/Shivani767/apertus-eval-prep/tree/master/tests)
[![License](https://img.shields.io/badge/License-MIT-green)](https://github.com/Shivani767/apertus-eval-prep/blob/master/LICENSE)

**Research dashboard:**
https://shivani767.github.io/apertus-eval-prep/

**Repository:**
https://github.com/Shivani767/apertus-eval-prep

---

# 1. What is Apertus Eval Prep?

**Apertus Eval Prep is a research and engineering system for measuring how evaluation choices affect LLM results.**

Most LLM evaluations look simple:

```text
Model → Benchmark → Score
```

But the actual experiment is more complicated:

```text
                    ┌─────────────┐
                    │    Model    │
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          ↓                ↓                ↓
       Prompt          Backend         Quantization
          ↓                ↓                ↓
    Few-shot          Decoding          Hardware
          └────────────────┼────────────────┘
                           ↓
                     Evaluation
                           ↓
                    Measured Result
```

Apertus makes these conditions explicit, records them as experiment metadata, runs controlled comparisons, stores the raw measurements, and performs statistical analysis on top of them.

The result is not just a number.

It is a **reproducible measurement with context**.

---

# 2. The Problem

LLM benchmark scores are often treated as if they were fixed properties of a model.

For example:

```text
Model A = 68%
Model B = 64%

Therefore Model A is better.
```

But what if Model A was evaluated with a different prompt?

What if Model B used a different chat template?

What if one evaluation used vLLM and another used Hugging Face Transformers?

What if one model was quantized?

What if the result came from one stochastic run?

What if changing the evaluation configuration reverses the ranking?

These are not theoretical concerns.

The experiments in this project show that they can happen.

---

# 3. Why Existing Evaluation Is Not Enough

Traditional benchmark workflows are optimized for answering:

> **"What score did this model get?"**

Apertus is interested in a harder question:

> **"How reliable is that score as evidence about the model?"**

Many evaluation pipelines make experimental configuration implicit.

A researcher may report:

```text
Qwen-3B → 64.38%
```

but the number may depend on:

* exact prompt wording
* number of demonstrations
* chat template
* decoding configuration
* inference backend
* quantization
* sampling seed
* hardware
* runtime implementation

If these factors are not recorded and controlled, two numbers that look comparable may not actually represent the same experiment.

### The key idea

Apertus treats:

```text
Model = Score
```

as an incomplete representation.

Instead:

```text
Model × Task × Evaluation Configuration
                  ↓
           Measured Result
```

The evaluation configuration is part of the measurement.

---

# 4. What I Built

I built a **configuration-driven evaluation and research platform** that turns LLM experiments into traceable, reproducible artifacts.

The system handles the complete workflow:

```text
Experiment Definition
        ↓
Configuration
        ↓
Evaluation Runner
        ↓
Model / Inference Backend
        ↓
Predictions
        ↓
Result Registry
        ↓
Statistical Analysis
        ↓
Research Findings
        ↓
Interactive Dashboard
```

Every experiment can be traced back through:

```text
Finding
   ↓
Report
   ↓
Result Registry
   ↓
Experiment Configuration
   ↓
Source Code
   ↓
Git Commit
```

This was an intentional engineering decision.

I did not want the research to depend on:

```text
"Run this notebook and hope you get the same number."
```

Instead, the goal is:

> **A result should be reproducible evidence, not just a number copied into a paper.**

---

# 5. What Are We Actually Studying?

The project investigates **evaluation sensitivity**.

The main research question is:

> **How sensitive are LLM benchmark results and model rankings to reasonable changes in evaluation and inference configuration?**

The experiments study several dimensions.

| Factor                | What we are testing                                     |
| --------------------- | ------------------------------------------------------- |
| **Prompting**         | Does wording change measured capability?                |
| **Few-shot examples** | Do demonstrations help consistently?                    |
| **Chat templates**    | Can formatting change results?                          |
| **Inference backend** | Does the serving implementation affect measurements?    |
| **Quantization**      | What happens to quality under lower precision?          |
| **Decoding**          | How sensitive are results to generation settings?       |
| **Sampling**          | How much variation comes from stochastic generation?    |
| **Hardware/runtime**  | How does the execution environment affect measurements? |
| **Thinking mode**     | Does reasoning configuration change results?            |
| **Hallucination**     | How reliable are generated answers?                     |
| **Safety**            | How does behavior change on safety-oriented tasks?      |
| **Cost**              | What quality/cost trade-offs appear?                    |
| **Latency**           | What performance cost accompanies a configuration?      |
| **Ranking**           | Does the "best model" remain the best?                  |

This turns evaluation from a single benchmark number into an **experimental system**.

---

# 6. Research Design

The core experiments use a controlled **one-factor-at-a-time (OFAT)** design.

We start with a frozen baseline:

```text
Model
Task
Prompt
Backend
Quantization
Decoding
Runtime
```

Then change one factor.

For example:

```text
                BASELINE
                   │
        ┌──────────┼──────────┐
        ↓          ↓          ↓
      Prompt     Backend   Quantization
        ↓          ↓          ↓
      Result     Result     Result
        └──────────┼──────────┘
                   ↓
          Statistical Analysis
                   ↓
           Ranking Stability
```

This design was chosen because it makes attribution easier.

If the score changes after changing only the prompt, we have much stronger evidence that the prompt contributed to the change.

The architecture can later support factorial and interaction studies when multiple factors need to be studied simultaneously.

---

# 7. The Most Important Finding

One of the clearest findings is **prompt sensitivity**.

The same Qwen-3B model produced:

```text
Concise prompt
      ↓
   51.25%

5-shot prompt
      ↓
   68.63%
```

That's a:

## +17.38 percentage-point difference

without changing the underlying model.

The effect is not even consistent across models.

### Control vs 5-shot

| Model   |    Control |     5-shot |       Change |
| ------- | ---------: | ---------: | -----------: |
| SmolLM2 |     39.75% |     34.25% |     -5.50 pp |
| Qwen-3B |     64.38% | **68.63%** | **+4.25 pp** |
| Phi-3.5 | **67.00%** |     56.38% |    -10.63 pp |

This tells us something important:

> **A prompting strategy cannot automatically be assumed to improve every model.**

---

# 8. The Stronger Finding: Rankings Can Reverse

This is more interesting than a score changing.

Under the control configuration:

```text
1. Phi-3.5     67.00%
2. Qwen-3B     64.38%
3. SmolLM2     39.75%
```

Under 5-shot prompting:

```text
1. Qwen-3B     68.63%
2. Phi-3.5     56.38%
3. SmolLM2     34.25%
```

The top-ranked model changes.

That means:

> **The answer to "which model is best?" can depend on how the evaluation is configured.**

This is the central research motivation behind Apertus.

The project is therefore not trying to create another leaderboard.

It is trying to understand **how trustworthy the conclusions behind a leaderboard are**.

---

# 9. Backend Sensitivity

The project also investigates whether the inference implementation itself can affect evaluation results.

With the model, task and prompt held fixed:

| Model   | Hugging Face |   vLLM |   Difference |
| ------- | -----------: | -----: | -----------: |
| SmolLM2 |       39.75% | 42.00% |     +2.25 pp |
| Qwen-3B |       64.38% | 66.75% | **+2.38 pp** |
| Phi-3.5 |       67.00% | 67.13% |     +0.13 pp |

The result is not:

> "vLLM is better."

The more useful conclusion is:

> **The inference backend is itself an experimental variable and should be recorded when comparing LLM evaluation results.**

The effect is measurable, but model-dependent.

---

# 10. Quantization

Apertus also studies whether lower-precision inference changes evaluation outcomes.

For Qwen-3B:

| Configuration | Accuracy |
| ------------- | -------: |
| INT8          |   64.75% |
| INT4          |   65.63% |

For Phi-3.5:

| Configuration | Accuracy |
| ------------- | -------: |
| Control       |   67.00% |
| INT8          |   67.25% |
| INT4          |   69.88% |

The purpose is **not** to claim that INT4 is universally better.

The research question is:

> **Does quantization change measured model behavior, and is that effect consistent across models and tasks?**

This distinction matters when evaluating models that will eventually run under constrained memory or inference budgets.

---

# 11. Sampling Stability

LLM evaluation can also change because generation is stochastic.

For example, repeated SmolLM2 runs under controlled sampling produced:

```text
Seed 0 → 36.25%
Seed 1 → 37.63%
Seed 2 → 39.00%
```

Qwen-3B produced:

```text
Seed 0 → 64.25%
Seed 1 → 65.00%
Seed 2 → 63.00%
```

Instead of reporting only one number, Apertus records repeated measurements.

This allows us to ask:

> **Is the observed difference larger than the normal variation of the evaluation process?**

---

# 12. Beyond Accuracy

A production LLM system is rarely optimized for accuracy alone.

A real engineering decision may look like:

```text
        Quality
           +
      Reliability
           +
         Latency
           +
        Memory
           +
          Cost
```

Apertus therefore includes infrastructure for:

* accuracy
* failure analysis
* hallucination
* safety
* reasoning/thinking behavior
* latency
* throughput
* TTFT
* memory
* evaluation cost
* quality/latency Pareto analysis
* ranking stability

This makes the project useful not only for research benchmarking, but also for **choosing practical model configurations for deployment**.

---

# 13. Architecture

```text
┌─────────────────────────────┐
│ Experiment Configuration     │
│ YAML / CLI / parameters      │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│ Evaluation Orchestrator      │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│ Model + Inference Backend    │
│ HF / vLLM / other runtimes   │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│ Task Evaluation              │
│ Predictions + measurements   │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│ Result Registry              │
│ Config + predictions + meta  │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│ Statistical Analysis         │
│ CI / bootstrap / tests       │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│ Reports + Dashboard          │
└─────────────────────────────┘
```

---

# 14. Why These Technologies?

The technology choices are driven by research and engineering requirements, not by trying to maximize the number of technologies in the stack.

### Python

Python is the primary language because the project needs direct access to the ML ecosystem, model runtimes, statistical tooling, experiment automation and data processing.

### YAML / Configuration Files

Experiments are configuration-driven so that changing a prompt, backend or quantization setting does not require rewriting evaluation code.

This reduces accidental differences between experiments.

### Hugging Face Transformers

Used as a standard model execution path and reference inference implementation.

This provides a familiar baseline for comparing other serving backends.

### vLLM

Used to study how a production-oriented inference runtime affects evaluation and to expose quality/performance trade-offs that may not appear under a single inference implementation.

### JSONL Result Registry

Results are stored as structured records because experiments need to be queried, compared, audited and regenerated.

A registry also prevents results from living only inside notebooks.

### Statistical Testing

The project uses paired tests, bootstrap confidence intervals, permutation tests and multiple-comparison corrections because a raw score difference is not automatically evidence of a meaningful difference.

### Git + Artifact Verification

Research results need provenance.

The project therefore connects results to configurations, artifacts and source-code versions.

### React + TypeScript Dashboard

The web dashboard makes the research inspectable without requiring someone to understand the Python implementation first.

---

# 15. Failure Modes

A serious evaluation system should also tell us when something went wrong.

Apertus explicitly distinguishes:

```text
runtime_error
empty_output
unparseable
wrong_answer
correct
```

This matters because:

```text
0%
```

can mean very different things.

For example:

* the model answered incorrectly,
* the model returned nothing,
* generation failed,
* the answer could not be parsed,
* the runtime crashed.

These should not silently become the same statistic.

The project therefore keeps failure information separate from measured accuracy.

---

# 16. Research Reliability

The analysis layer includes:

* confidence intervals
* paired statistical testing
* paired bootstrap confidence intervals
* permutation testing
* McNemar's test where appropriate
* Holm-Bonferroni correction
* Benjamini-Hochberg FDR correction
* Kendall's τ for ranking stability
* seed stability
* configuration stability
* failure taxonomy
* runtime profiling
* Pareto analysis

There is also a **provisional Evaluation Reliability Score (ERS)**.

ERS is intended to answer:

> **How stable is the observed model ranking under the tested evaluation conditions?**

It combines multiple stability signals rather than relying on a single benchmark score.

Importantly, ERS is currently treated as a **research diagnostic**, not as a universally validated metric.

That distinction is intentional.

---

# 17. Evaluation Dashboard

The project has a live research dashboard:

## [Open the Apertus Eval Dashboard →](https://shivani767.github.io/apertus-eval-prep/)

The dashboard is designed around the question:

> **How robust are conclusions about relative LLM capability to reasonable changes in evaluation configuration?**

It provides:

* Overview
* Key research finding
* Experiment Explorer
* Experiment Details
* Ranking Stability
* Results Matrix
* Statistical Evidence
* Reliability analysis
* Failure analysis
* Cost/Pareto analysis
* Sampling analysis
* Reproducibility checks
* Methodology
* Limitations

The dashboard is generated from the committed research artifacts rather than maintaining a separate hand-written dataset.

---

# 18. Reproducibility

Apertus treats reproducibility as part of the product rather than documentation added at the end.

The workflow is:

```text
Configuration
      ↓
Run
      ↓
Raw Measurement
      ↓
Registry
      ↓
Verification
      ↓
Analysis
      ↓
Report
```

Another researcher should be able to determine:

```text
What was run?
Which model?
Which configuration?
Which data?
Which code version?
What was measured?
How was the result derived?
```

Missing measurements are never silently replaced with estimates.

---

# 19. Current Research Status

### Experimental matrix

**34 / 34 cells complete**

**100% of the planned paper experiment matrix**

The completed matrix covers the project's core controlled comparisons across models and evaluation configurations.

### Engineering status

* **Research matrix:** 34/34 complete
* **Automated tests:** 124 passing
* **Statistical methodology:** implemented
* **Result registry:** committed
* **Reproduction CLI:** available
* **Artifact verification:** implemented
* **Failure taxonomy:** implemented
* **Runtime profiling:** implemented
* **Ranking stability:** implemented
* **Pareto analysis:** implemented
* **Research dashboard:** deployed
* **Paper artifacts:** generated
* **Validation documentation:** available

> **Only measured and committed results are presented as experimental findings.**

---

# 20. Research Dashboard

### Live demo

**https://shivani767.github.io/apertus-eval-prep/**

Use the dashboard to explore:

```text
Model
 ↓
Configuration
 ↓
Result
 ↓
Ranking
 ↓
Statistical Evidence
 ↓
Reliability
 ↓
Failure / Cost / Runtime Analysis
```

This is the easiest way to understand the project without reading the entire codebase.

---

# 21. Repository Structure

```text
apertus-eval-prep/
│
├── configs/                 # Experiment configurations
├── data/                    # Evaluation data
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── RESEARCH_PLAN.md
│   ├── RESEARCH_AUDIT.md
│   ├── STATISTICAL_METHODOLOGY.md
│   ├── VALIDATION.md
│   ├── METAMORPHIC_EVAL.md
│   └── EVALUATION_COST.md
│
├── notebooks/               # Research analysis
├── paper/                   # Paper materials
├── reports/                 # Generated research reports
│
├── results/
│   ├── registry_paper.jsonl
│   └── runs/
│
├── scripts/                 # Experiment utilities
│
├── src/
│   └── apertus_eval_prep/
│       ├── cli.py
│       ├── config.py
│       ├── run_eval.py
│       ├── sweep.py
│       ├── registry.py
│       ├── stats.py
│       ├── stability.py
│       ├── ranking.py
│       ├── reliability.py
│       ├── fragility.py
│       ├── variance.py
│       ├── adaptive.py
│       ├── cost.py
│       ├── failures.py
│       ├── profile.py
│       ├── pareto.py
│       ├── dashboard.py
│       ├── reproduce.py
│       ├── metamorphic.py
│       └── report.py
│
├── frontend/                # Research dashboard
├── tests/                   # Automated tests
│
├── Dockerfile
├── Makefile
├── CITATION.cff
├── pyproject.toml
└── README.md
```

---

# 22. Quick Start

```bash
git clone https://github.com/Shivani767/apertus-eval-prep.git
cd apertus-eval-prep

python3 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
```

Run tests:

```bash
pytest -q
```

Run a smoke evaluation:

```bash
python -m apertus_eval_prep eval \
    --config configs/smoke.yaml \
    --out results/smoke.json
```

Generate research artifacts:

```bash
make paper
make figures
```

Run the research dashboard locally:

```bash
python -m apertus_eval_prep dashboard
```

Reproduce and verify a specific experiment:

```bash
python -m apertus_eval_prep reproduce \
    --run-id <run_id> \
    --check
```

---

# 23. Product Perspective

Apertus is not intended to replace every LLM benchmark.

It solves a different problem.

### Traditional evaluation asks:

> **Which model scores highest?**

### Apertus asks:

> **How stable is that conclusion when reasonable parts of the evaluation system change?**

This matters when choosing models for:

* research
* production systems
* inference infrastructure
* quantized deployments
* cost-sensitive applications
* agentic systems
* AI coding systems
* model selection

A model that wins under one configuration but loses under another may require a different engineering decision from a model whose ranking is stable.

---

# 24. Future Improvements

The next research direction is to move beyond isolated one-factor changes and study **interactions between evaluation variables**.

For example:

```text
Prompt
   ×
Backend
   ×
Quantization
   ×
Model
```

Future work includes:

### Larger model coverage

Evaluate more model families, sizes and instruction-tuning approaches.

### More tasks

Extend beyond the current evaluation suite to reasoning, coding, multilingual and agentic workloads.

### Interaction effects

Study whether prompt × backend × quantization combinations create effects that cannot be explained by one factor alone.

### Adaptive evaluation

Instead of measuring every possible configuration, identify which configurations provide the most information about ranking stability.

### Cost-aware evaluation

Study:

```text
Quality
   ×
Reliability
   ×
Latency
   ×
Memory
   ×
Cost
```

to determine how much evaluation is actually necessary before making a model-selection decision.

### AI for Software Engineering

Apply the same methodology to:

* code generation
* code repair
* repository-level reasoning
* bug fixing
* test generation
* coding agents
* static-analysis-assisted evaluation

The central question remains the same:

> **Can we trust the conclusion produced by the evaluation pipeline?**

---

# 25. Research Contribution

The project is built around one central claim:

> **An LLM benchmark score is not simply a property of the model. It is a measurement produced by the model under a particular evaluation configuration.**

The experiments provide concrete evidence that changing evaluation conditions can:

* materially change scores,
* affect different models differently,
* reverse model rankings,
* introduce stochastic variation,
* change quality/efficiency trade-offs,
* and influence practical model-selection decisions.

Apertus provides the infrastructure to **measure these effects rather than assume them away**.

---

# 26. What I Own in This Project

This project combines research and systems engineering.

I designed and implemented the evaluation pipeline, experiment configuration system, result registry, statistical analysis layer, artifact verification, failure analysis, runtime profiling, reproducibility workflow, and research dashboard.

The important engineering principle throughout the project is:

> **Make every research conclusion traceable to a measurement.**

That means the system is designed around:

```text
Experiment
    ↓
Measurement
    ↓
Evidence
    ↓
Analysis
    ↓
Conclusion
```

rather than:

```text
Experiment
    ↓
Interesting number
    ↓
Claim
```

---

# 27. Why This Project Exists

LLM systems are becoming increasingly complex.

A model is no longer just a set of weights.

Its observed behavior can depend on:

```text
Model
+
Prompt
+
Context
+
Inference Runtime
+
Precision
+
Decoding
+
Hardware
+
Evaluation Method
```

As these systems become more complex, reliable evaluation becomes increasingly important.

**Apertus Eval Prep is my attempt to build the infrastructure needed to study that problem systematically.**

---

# Citation

If you use the framework, methodology or research artifacts:

```bibtex
@software{bhandari_apertus_eval,
  author = {Bhandari, Shivani},
  title = {Apertus Eval Prep: Configuration-Sensitive LLM Evaluation},
  year = {2026},
  url = {https://github.com/Shivani767/apertus-eval-prep}
}
```

---

# Author

**Shivani Bhandari**

AI/ML Research · LLM Evaluation · ML Systems · Inference · Software Engineering

GitHub: https://github.com/Shivani767

Research Dashboard:
https://shivani767.github.io/apertus-eval-prep/

---

## One-line summary

> **Apertus Eval Prep studies how much of an LLM benchmark result comes from the model — and how much comes from the way we evaluate it.**
