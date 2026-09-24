# Phase 3 synthetic episode evaluation report

> **Evidence class: `MOCK`**
>
> This is a deterministic, synthetic pipeline-validation report generated with the offline mock adapter. It is not a real model benchmark result and must not be used as a claim about model quality or production safety.

## Scope

- Configurations: `configs/platform_phase3_rag.yaml`, `configs/platform_phase3_agent.yaml`
- Fixtures: `data/platform_episodes.jsonl`
- Episodes: 5 English-only synthetic cases covering customer-support RAG, contradictory policy, tool use, tool-failure recovery, and sanitized retrieval-injection detection.
- Tools: offline simulated tool calls and deterministic recovery behavior.
- Network/API/GPU: not required.

## RAG slice

| metric | value |
|---|---:|
| episode_count | 5 |
| task_completion_rate | 1.0000 |
| groundedness_mean | 0.9652 |
| tool_schema_validity | 1.0000 |
| tool_sequence_validity | 1.0000 |
| unnecessary_tool_call_count | 0 |
| recovery_success_rate | 1.0000 |
| step_count_mean | 1.8000 |
| end_to_end_latency_ms_mean | 117.6142 |
| unsupported_claim_rate | 0.0348 |
| source_citation_coverage | 1.0000 |
| unsafe_action_count | 0 |
| usage_reported | true |
| input_tokens | 557 |
| output_tokens | 90 |
| token_count | 647 |

## Agent slice

| metric | value |
|---|---:|
| episode_count | 5 |
| task_completion_rate | 1.0000 |
| groundedness_mean | 0.9652 |
| tool_schema_validity | 1.0000 |
| tool_sequence_validity | 1.0000 |
| unnecessary_tool_call_count | 0 |
| recovery_success_rate | 1.0000 |
| step_count_mean | 1.8000 |
| end_to_end_latency_ms_mean | 117.6142 |
| unsupported_claim_rate | 0.0348 |
| source_citation_coverage | 1.0000 |
| unsafe_action_count | 0 |
| usage_reported | true |
| input_tokens | 250 |
| output_tokens | 90 |
| token_count | 340 |

## Perturbation coverage

The deterministic perturbation framework includes:

- removal of key evidence;
- irrelevant distractor context;
- contradictory and stale sources;
- context truncation;
- retrieval failure;
- simulated tool timeout/error;
- sanitized retrieval prompt-injection detection text.

Perturbations are safe abstractions for detector testing, not operational misuse instructions.

## Artifact layout

Each run writes an immutable directory containing:

```text
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
gate_report.json
report.md
report.html
```

Raw requests/responses and tool observations remain separate from derived scores and aggregates. Tool arguments, results, and traces are redacted before persistence.

## Reproduction

```bash
PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-episode \
  --config configs/platform_phase3_rag.yaml \
  --out runs/phase3-rag

PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-episode \
  --config configs/platform_phase3_agent.yaml \
  --out runs/phase3-agent
```

## Limitations

- Quality, groundedness, citation support, and tool behavior are deterministic heuristics, not human adjudication.
- The five fixtures are small and synthetic; results are not statistically representative of production workloads.
- Tool traces are consumed by the evaluator; this is not a full agent runtime or production orchestration framework.
- Missing usage or citation evidence is reported as unavailable, not as a measured zero.
- High-impact deployments require representative retrieval corpora, real tool sandboxes, human review, and threat modeling.
