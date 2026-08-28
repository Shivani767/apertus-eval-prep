# Related work

This document positions **apertus-eval-prep** against existing LLM evaluation infrastructure. The goal is not to claim superiority without evidence, but to state what this framework **investigates** that general harnesses typically treat as operator noise.

---

## Existing frameworks

| Framework | Primary focus | Config sensitivity as first-class? | Ranking stability stats? | Frozen generative replay? |
|---|---|---|---|---|
| [EleutherAI lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness) | Broad benchmark suite, loglikelihood + generative tasks | Partial (task YAML) | No | Task configs pinned; backend varies by operator |
| [HELM](https://crfm.stanford.edu/helm/) | Holistic leaderboards, many metrics | Documented but not OFAT-ablated | Limited | Fixed prompts; infrastructure differs by deployment |
| [OpenAI Evals](https://github.com/openai/evals) | Custom eval registry | Per-eval | No | Varies by eval |
| [LightEval](https://github.com/huggingface/lighteval) | HF-native fast eval | Model/task config | No | Hub datasets |
| [Inspect](https://github.com/UKGovernmentBEIS/inspect_ai) | Agentic/sandbox evals | Run config | No | Reproducible runs; different task family |
| [swiss-ai evals-post-train](https://github.com/swiss-ai/evals-post-train) | Post-training evals (incl. HF vs vLLM notes) | Serving-aware | No | Generation-sensitive tasks documented |

---

## Benchmark families used here

| Benchmark | Origin | This repo's use |
|---|---|---|
| ARC-Easy | AI2 ARC | Generative letter (not loglikelihood) |
| GSM8K | Cobbe et al. | Last-number exact match |
| HellaSwag | Zellers et al. | Generative letter |
| MGSM | Shi et al. | Multilingual numeric EM |
| Paraphrase / robustness / hallucination / safety | **Original frozen slices** | Small n probes; not leaderboard claims |

---

## What this project investigates

> **How sensitive are LLM evaluation scores and model rankings to evaluation configuration?**

Specifically, under **one-factor-at-a-time (OFAT)** ablations on a frozen generative protocol:

| Factor | Example levels |
|---|---|
| Chat template | tokenizer / none / mismatched |
| Prompt | default / concise / 5-shot |
| Backend | Hugging Face generate / vLLM |
| Precision | fp16 / int8 / int4 |
| Seed / sampling | greedy seeds / T=0.7 |
| Thinking mode | wrapper on / off |
| Paraphrase | orig / p1 / p2 |

**Measured outcomes:** absolute accuracy (Wilson CI), paired score change (McNemar), rank order change (Kendall τ_b, reversals), cost/latency derivatives.

---

## What existing frameworks do not emphasize (our niche)

1. **Generative exact-match replay** with identical rendered strings across HF and vLLM (no double chat template).
2. **Explicit incomparability** — hardware, dtype, and slice documented in every JSON manifest.
3. **Interval-aware ties** — overlapping Wilson CIs reported as ties even when point estimates differ.
4. **Unified registry** — `config_hash` dedup, partial checkpoint resume, Colab → git workflow.
5. **Multi-dimensional probes** on one harness (multilingual + robustness + safety + hallucination canary) without conflating with official n=800 matrix.

---

## What we do not claim

- We do not replace lm-eval for leaderboard scale or loglikelihood MCQ.
- We do not provide comprehensive safety red-teaming (6-item canary only).
- We do not implement LLM-as-judge hallucination detection.
- We have not completed the full 34-cell T4 matrix (19/34 at last audit).

---

## Suggested contribution statements (evidence-dependent)

1. *A reproducible OFAT protocol showing that generative benchmark scores and rankings move under legitimate configuration changes (prompt, backend, template), with paired statistics on frozen official slices.*

2. *An experiment registry and manifest design that makes evaluation configuration a named, hashable part of the measurement — not operator noise.*

3. *Empirical demonstration that rank reversals and score shifts are distinct claims: McNemar can reject equality while Kendall τ remains undefined or equal to 1.0.*

These should only appear in a paper when backed by committed `results/runs/*.json` rows.

---

## References

- Clark et al. (2018). Think you have Solved Question Answering? Try ARC.
- Cobbe et al. (2021). Training Verifiers to Solve Math Word Problems (GSM8K).
- Shi et al. (2022). Language Models are Multilingual Chain-of-Thought Reasoners (MGSM).
- Liang et al. (2022). Holistic Evaluation of Language Models (HELM).
- Gao et al. (2023). A framework for few-shot language model evaluation (lm-eval).
