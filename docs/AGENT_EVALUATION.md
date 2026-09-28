# Agent evaluation and regression

Episode execution already exists: `core/episode_runner.py` runs offline
RAG/agent episodes, `tasks/rag_episode.py` defines `Episode` and `ToolTrace`,
`evaluators/tool_use.py` scores tool use and recovery, and `platform-episode`
writes the `system` metrics block. This document covers the layer added on top:
what was tested, what regressed, and whether a declared policy accepts the
change.

## The three questions

| Question | Function |
|---|---|
| What was tested? | `scenario_coverage` |
| Did anything regress? | `compare_agent_runs` |
| Does the declared policy accept it? | `evaluate_regression_policy` |

## Scenario taxonomy

`SCENARIO_CLASSES` covers eleven classes: `happy_path`, `ambiguous_request`,
`missing_information`, `tool_failure`, `malformed_tool_output`,
`conflicting_information`, `long_context`, `repeated_request`,
`adversarial_input`, `policy_boundary`, `recovery`.

Not every class applies to every agent, so `applies` is **declared per
scenario** and is mandatory — a missing `applies` is an error, not a default.
An agent with no long-context path marks `long_context` as not applicable
instead of carrying a permanent untested gap. Not-applicable scenarios are
**excluded from the coverage denominators**, not counted as failures.

## Coverage is not quality

Three numbers are reported and never merged:

| Metric | Definition |
|---|---|
| `count_coverage` | applicable scenario classes declared / taxonomy size |
| `execution_coverage` | declared applicable scenarios executed / declared applicable |
| `success_rate_of_executed` | succeeded / (succeeded + failed) among executed |

A suite can have `execution_coverage = 1.0` and a success rate near zero; that
is a *well-covered, failing* agent, and the artifact says so. `untested_scenarios`
and `failed_scenario_ids` name the specifics rather than leaving them in a
ratio. A scenario that ran but produced no pass/fail signal is counted in
`executed_without_signal` and excluded from the success denominator — an absent
signal is not a pass.

## Regression comparison

`compare_agent_runs` reports `baseline`, `candidate` and `delta` per named
metric, with a `direction` per metric. Direction matters: a latency increase is
a **regression** even though the raw delta is positive, and
`unsafe_action_rate` is lower-is-better for the same reason. Each metric is
`improved`, `regressed`, `unchanged` or `not_comparable`.

A metric either run did not report is `not_comparable` with `delta: null` — never
a delta of zero. Tokens and tool calls are normalised to per-episode means.

## Regression policy

Thresholds live in data (`configs/agent/regression_policy.yaml`):

```yaml
regression_policy:
  task_success:
    minimum_delta: -0.02
  latency_ms_mean:
    maximum_relative_increase: 0.20
```

Two rule forms: `minimum_delta` (worst acceptable signed change) and
`maximum_relative_increase` (budget, as a ratio against the baseline). Gating a
metric that is not compared, or a rule with no threshold, is an error.

### Verdicts

| Verdict | Meaning |
|---|---|
| `PASS` | every gated metric met its declared threshold |
| `FAIL` | at least one **measured** metric violated its threshold |
| `INCONCLUSIVE` | a gated metric could not be evaluated |

`INCONCLUSIVE` covers two distinct cases, each with its own reason: the metric
was not reported by both runs, or the declared rule is undefined for its value
(a `maximum_relative_increase` rule against a zero baseline). **A missing metric
can never satisfy a gate.** `FAIL` outranks `INCONCLUSIVE`, because a measured
breach is a fact while a missing metric is only an evidence gap.

The output is labelled `result_type: "policy gate result"`. It is an
engineering policy aid and **not** production approval, not a safety
certification, and not evidence the agent is safe in general.

## Usage

```bash
apertus-eval-prep agent-regression \
  --baseline results/runs/<baseline> \
  --candidate results/runs/<candidate> \
  --policy configs/agent/regression_policy.yaml \
  --evidence-mode MOCK

apertus-eval-prep scenario-coverage \
  --scenarios configs/agent/scenarios.yaml \
  --outcomes reports/outcomes.json
```

`--evidence-mode` is an explicit choice from the canonical list, defaulting to
`UNKNOWN`; a MOCK agent run cannot be reported as a real-model result.

## What this does not claim

A clean gate means the candidate met a declared policy on the evaluated
episodes. It does not establish that the agent is safe, correct in general, or
ready for production. Coverage numbers describe what the suite exercised, not
what the agent can do. A comparison is only valid over the same scenarios on
both sides; comparing runs over different scenario sets is not a regression
test, and the artifacts do not check that for you.
