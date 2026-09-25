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
