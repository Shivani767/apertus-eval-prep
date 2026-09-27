# Frequently Asked Questions

## Is this a benchmark?

No, and that is deliberate. A benchmark answers "what is the score"; this platform answers
"under what conditions, and how stable is that score". It is a framework for producing
reproducible, evidence-labelled evaluations, and it ships one curated multi-model study as
worked evidence rather than a leaderboard.

If you want a single number for a model, this is the wrong tool. If you want to know whether
a ranking survives a change of prompt, backend, seed, or quantization, it is the right one.

## Does it run real models?

Yes, optionally. Real open-weight models run through the `local_transformers` adapter
(`LOCAL_REAL_MODEL` evidence). This requires the `real-model` extra:

```bash
pip install -e ".[real-model]"    # torch, transformers, accelerate
```

The default and CI path is the deterministic `mock` adapter, which needs none of that.

## Does it require a GPU or API keys?

No. The base install has one runtime dependency (`pyyaml`). The offline path imports no GPU
runtime — verified: importing the CLI pulls in none of `torch`, `transformers`, `vllm`, or
`accelerate`. CI runs CPU-only, offline, with no API keys and no model downloads.

API keys are only relevant if you write an adapter for a hosted provider.

## What does MOCK evidence mean?

That a deterministic fixture was executed to validate the **framework**: artifacts are
written, metrics and confidence intervals are computed, fingerprints group, reports render,
gates evaluate.

It means **nothing about any model**. A `MOCK` score is not a benchmark result and a `MOCK`
latency is not a hardware measurement. The label travels with the artifact so the two are
never confused.

## What does a release gate mean?

A release gate evaluates a run against thresholds **this repository defines**, in a YAML
policy under `configs/release_gates/`. A passing gate means the run met your declared
thresholds.

It is **not** production approval, and it is not a safety certification. The gate payload
carries that disclaimer in its own output. Real production approval requires organizational
governance, deployment monitoring, privacy and security review, and human sign-off.

## Can it evaluate RAG and agents?

Yes. `platform-episode` runs episode-level evaluation over RAG and agent workflows, with
tool traces, retrieval groundedness, turn budgets, and outcome classification. See
`docs/AGENT_RAG_EVALUATION.md`.

One caveat worth repeating: groundedness is a **lexical-support heuristic**, suitable for
offline CI. It measures whether an answer is supported by the retrieved context; it does not
measure factuality.

## Does it prove safety?

No. `platform-safety` runs an automated red-team suite over a declared taxonomy and reports
attack success, category pass rates, false refusal, and severity-weighted risk.

That is evidence about a specific, declared test suite on specific models under specific
conditions. It is not a safety certification, it does not generalize to categories the suite
has not tested, and no gate result here should be presented as an assurance of safety.

## How do I run it in Colab?

Open one of the generated notebooks from GitHub and run the cells top to bottom:

1. Open the notebook directly from the repository, or save a copy to Drive.
2. **Runtime → Change runtime type → T4 GPU**, then **Restart session**.
3. Run all cells. Section 0 is the authentication and access preflight for gated models.
4. The final section exports a zip; download it.

For gated repositories (Gemma, Llama), accept the licence on huggingface.co while signed in
as the account that runs the notebook, create a read-only token, and add it as the Colab
secret `HF_TOKEN`. Never paste a token into a notebook cell. The preflight validates the
token against an authenticated endpoint and proves the download works before any GPU time is
spent, so an access problem stops the session in seconds instead of after 257 failures.

Full instructions: `docs/COLAB_EXPERIMENT_GUIDE.md`.

## How do I use real models?

Two ways.

**Interactively**, via the notebooks described above.

**Programmatically**, with a config whose adapter is not `mock`:

```bash
pip install -e ".[real-model]"
python -m apertus_eval_prep platform-run --config my_config.yaml --out runs/real
```

Pin the revision to a commit SHA. A run recorded against `main` cannot be reproduced from its
manifest alone, and the summary warns you about exactly that.

## How do I contribute?

Read [CONTRIBUTING.md](../CONTRIBUTING.md), then open an issue describing the change. The
useful contributions are usually the unglamorous ones: a task or evaluator, a safety
category with a defensible severity weight, a gate policy, a study configuration, a bug
reproduced in a test, or documentation that removes an overstatement.

Please read the [Code of Conduct](CODE_OF_CONDUCT.md) first, and note the extra care needed
when discussing model outputs on sensitive topics.


## Why do some models score 0.0000?

Because the harness sends raw text and does not apply the model's chat template, while the
task asks for a single letter. A model that answers "The correct answer is c. the human
heart's primary function is..." is marked wrong because the extraction reads the first
token.

This is a **protocol** limitation, not a capability finding, and the committed
`scored_examples.jsonl` files contain worked examples. Correcting it changes
`metric_definition_version` and requires re-running every model — it is a protocol decision,
not a reporting fix. See `results/colab_real_model/README.md`.

## Can I compare two of my own runs?

Yes, with `platform-compare`. It refuses to compare runs whose identity differs (dataset,
task, prompt, or metric definition), which prevents the most common way evaluation results
get misread.

## What is a failure fingerprint?

A stable grouping of failures that does not change when the prompt identity changes, plus
investigation priorities. It is a **triage aid**: it tells you where to look first. The
priorities derive from severity, failure rate, and baseline delta, and they do not establish
causation.

## Is my data safe to commit?

Only after you read it. `raw_outputs.jsonl` preserves what the model actually said, which is
what makes the work reproducible and also the most likely place for sensitive content to
appear. Redaction in this repository is pattern-based and reduces risk; it does not prove a
payload is anonymous. See [SECURITY.md](../SECURITY.md) and
[docs/SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md).

## What license is this under?

Apache License 2.0 — see [LICENSE](../LICENSE).
