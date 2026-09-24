# RAG and agent evaluation

RAG/agent fixtures model a user request, context sources, optional tools, constraints, success criteria, and a safe expected behavior. The runner records each tool call, schema validation result, status, latency, error type, timestamp, and recovery metadata in `tool_traces.jsonl`.

Offline metrics include task completion, tool-schema validity, tool-sequence validity, unnecessary calls, recovery success, step count, end-to-end latency, token/cost availability, observed unsafe-action count, groundedness, unsupported-claim rate, and source/citation support. The default groundedness evaluator is a transparent lexical-overlap heuristic; it is not an LLM judge or human adjudication. Missing usage or citation evidence remains `null`/unavailable rather than being reported as a measured zero.

## Sample report

A committed, synthetic sample is available at [`reports/phase3/synthetic_episode_report.md`](../reports/phase3/synthetic_episode_report.md). It is generated from the deterministic mock and must not be interpreted as a real model benchmark.

## Perturbations

The deterministic framework supports removing key evidence, adding distractors, contradictory/stale sources, truncation, retrieval failure, tool timeout/error, and a sanitized prompt-injection-like detector string. Perturbations are safe abstractions intended for detection testing, not operational misuse instructions.

Example:

```bash
PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-episode \
  --config configs/platform_agent.yaml --out runs/agent

# complete five-fixture Phase 3 slice (RAG)
PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-episode \
  --config configs/platform_phase3_rag.yaml --out runs/phase3-rag

# complete five-fixture Phase 3 slice (agent/tool traces)
PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-episode \
  --config configs/platform_phase3_agent.yaml --out runs/phase3-agent
```

The five-fixture slice covers customer-support RAG, contradictory policy, tool use, tool-failure recovery, and sanitized retrieval-injection detection. It is synthetic `MOCK` evidence and should not be described as a real model benchmark. The standard run report and failure fingerprint are written alongside `tool_traces.jsonl`; rebuild them with `platform-report` and `platform-fingerprint` without rerunning the adapter.

For production RAG/agent claims, add real tool sandboxes, representative retrieval corpora, trace retention controls, human review, and adversarial testing under an organizational threat model.
