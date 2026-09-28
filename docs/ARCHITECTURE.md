# Architecture

## Typed platform path

`core.schemas.RunSpec` is the validated source of truth. It contains adapter, prompt, task, decoding, runtime, evaluator, metrics, reporting, gate, evidence, and optional dimension settings. `core.config` resolves YAML inheritance and expands experiment matrices without mutating the original spec.

`core.runner` loads JSON/JSONL tasks, constructs an adapter, executes each example, scores it, and writes an immutable `RunStore` directory. `core.episode_runner` extends the same contract to RAG/agent steps and tool traces. `safety.runner` uses the same artifact/provenance boundary for sanitized safety cases.

## Artifact contract

```text
runs/<run_id>/
  manifest.json
  config.resolved.yaml
  dataset.lock.json
  prompts/prompt_protocol.json
  raw_outputs.jsonl
  scored_examples.jsonl
  tool_traces.jsonl
  metrics.json
  confidence_intervals.json
  failures.jsonl
  failure_fingerprint.json   aggregate observed failure profile
  gate_report.json
  report.md
  report.html
```

Raw observations are append-only and separate from derived scores. `RetentionPolicy` controls raw content; redaction is applied before persistence. Run directories are never silently overwritten. `failure_fingerprint.json` is a derived diagnostic artifact, not a replacement for the raw failure records.

## Extension boundaries

Tasks expose `Task`, adapters expose `ModelAdapter.complete()`, and evaluators consume typed records. Metrics are pure functions with explicit missing-data behavior. Release decisions are computed from metrics and versioned rules, not hidden in the CLI.


## Study and review layer

Phase 8 adds `study/` for validated study configuration, compatibility checks, aggregation, and escaped Markdown/HTML/CSV/JSON study outputs. `review/` provides privacy-safe sampling, template export, completed-annotation ingestion, reviewer anonymization, agreement summaries, and adjudication queues. These layers consume immutable Phase 1–7 artifacts and do not rerun or overwrite model evidence.

The legacy HF/vLLM path remains available as a compatibility layer. The typed platform is offline-first and uses no dashboard framework.

## Derived-analysis layer

The analyses below are **derived from already-committed measurements**. None of them runs a model, expands a matrix, or invents a cell. They read artifacts and report either a number with its denominator and its uncertainty, or an explicit refusal.

| Module | Responsibility | Key contract |
|---|---|---|
| `decision.py` | Decision stability: does a declared policy pick the same option everywhere? | delegates selection to `metrics.pareto.select_configurations`; a missing objective is `insufficient_evidence`, never 0 |
| `ranking.py` | Ordering agreement across configurations | adds `rank_reversal_rate`, `top_k_set_stability`; **no composite score** |
| `sensitivity.py` | Evaluation Sensitivity Index per factor | ESI computed only against a declared uncertainty scale; otherwise `null` with a reason |
| `factorial.py` | Interaction analysis over `interaction.py` designs | labels `ofat` / `factorial`; an OFAT design yields **no** interaction estimate |
| `variance.py`, `stats.py` | ANOVA, F tests, multiple-comparison corrections | `stats.f_sf` is dependency-free (regularized incomplete beta), verified against published critical values |
| `agent_reliability.py` | Scenario coverage, run comparison, regression policy gates | coverage counts stay split; a missing metric is `INCONCLUSIVE`, never a pass |
| `judge.py` | LLM-judge instrument reliability | a judge record may not declare `HUMAN_VALIDATED`; `is_ground_truth` is always false |
| `metamorphic.py` | Declared vs observed metamorphic relations | a missing observation is `insufficient_observation`, never `relation_violated` |
| `heldout.py` | Held-out configuration and leave-one-model-out generalization | train/heldout disjoint by construction; low power is stated, not hidden |
| `dashboard_sections.py` | Projects committed analysis artifacts into the site export | a missing artifact renders `not_generated`, **never** zero-filled |

### Shared conventions

- **The denominator is stated in the artifact.** A rate whose denominator is implicit cannot be audited, and the choice of denominator decides the number.
- **Missing is not zero.** An unmeasured input is `None`, `insufficient_evidence`, `not_comparable`, `INCONCLUSIVE` or `not_generated`, depending on the layer. It never becomes a passing value.
- **Refuse rather than approximate.** When a design cannot support an analysis, the artifact says `insufficient_design` with a reason instead of emitting a number that looks like a result.
- **No causal language.** Factor attribution carries a design-quality label and `causal_claim: false`.
- **Evidence tier is declared, never inferred upward.** Every new CLI takes `--evidence-mode` from the canonical list, defaulting to `UNKNOWN`.
