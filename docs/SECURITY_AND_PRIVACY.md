# Security and Privacy Posture

This document describes what the software does and does not protect. It is a technical
posture summary, not a compliance claim, and not a security guarantee. For reporting a
vulnerability, see [../SECURITY.md](../SECURITY.md).

## Threat model in one paragraph

The platform's realistic exposure is **data disclosure through committed artifacts**, not
remote exploitation. It is a research library that runs on a developer's machine or a
Colab VM, is not a network service, and exposes no listening port. What leaves your machine
is what you write to disk and choose to commit: prompts, model responses, and run metadata.

## Data flow

```text
  your config + your dataset
            |
            v
    adapter (mock | local_transformers | your own)
            |
            v
   run directory on disk  <-- the object with privacy risk
            |
            +--> report.md / report.html   (redacted before rendering)
            +--> review export JSONL       (sanitized)
            +--> git commit                (YOUR decision)
```

The framework performs no telemetry, no analytics, and no network calls of its own. The only
outbound traffic comes from real-model adapters reaching the Hugging Face Hub, and from the
gated-model preflight (`whoami` plus a single small file download).

## What is protected automatically

| Control | Where | What it does |
|---|---|---|
| Credential detection | `utils/pii.py` | Detects and redacts common credential shapes: `sk-`, `hf_`, `ghp_`, private-key headers, JWT-like strings, and `Authorization`-style values |
| PII redaction | `utils/pii.py` | Email addresses, phone numbers, credit-card-like digit runs |
| Structural redaction | `utils/pii.py` | Scrubs values under sensitive **keys** (`password`, `api_key`, `token`, `authorization`, …) even when the value does not match a value pattern |
| HTML escaping | `reporting/` | Dynamic content is escaped before rendering into `report.html` |
| Sanitized review export | `review/` | `platform-export-review` emits a reduced package rather than raw run content |
| Secret CI guard | `tests/test_no_secrets_committed.py` | Fails the build if a credential-shaped string is committed |
| Error-detail bounding | `adapters/` | Underlying load errors are redacted, single-line, and length-bounded before being written into artifacts |
| Token non-disclosure | `hub_auth.py` | Tokens are never logged, printed, or persisted; a validated token is published only into the process environment so a child process inherits it |

## What is **not** protected — read this part

**Pattern-based redaction is a reduction, not a guarantee.** It finds shapes it knows. It
cannot find:

- a secret in an unfamiliar format;
- a name, account, or identifier embedded in free text;
- content whose sensitivity is contextual and would only be obvious to a reader;
- personal data that does not look like PII.

The reports state this in their own text. Treat redaction as a first filter that lowers risk,
never as anonymization.

**Raw output retention is the main privacy risk.** `raw_outputs.jsonl` preserves what the
model actually said. That is the point — it is what makes a run auditable and a failure
debuggable — and it is also where sensitive content appears, because a model echoes whatever
it was given. If your prompts contain personal data, your artifacts contain it too.

Use `--no-raw` to disable raw retention when responses may be sensitive, and use
`platform-export-review` when you need to share a run with someone else.

**Prompts and datasets are not redacted by default at the input boundary.** The platform
records what you gave it so the run is reproducible. If an input is sensitive, it is your
responsibility not to commit the run, or to use `--no-raw` and a sanitized export.

## Retention and sharing guidance

1. Review the run directory before committing it. Read `raw_outputs.jsonl`.
2. Prefer `--no-raw` or a sanitized review export for anything you intend to share outside
   your team.
3. Never commit credentials. If one was ever pasted into a chat, an issue, or a commit,
   **revoke it** — deleting the message does not unpublish it.
4. Curated evidence under `results/` is published by design. It is reviewed for credential
   shapes and redacted where patterns matched, which is a floor and not a ceiling.

## Safety artifacts

The safety suite produces evaluations of how models behave under adversarial and sensitive
prompts. Handle the output defensively:

- It is research material for authorized testing.
- Generated harmful content should not be republished as illustration or marketing.
- A passing safety gate is not a safety certification.

## Supply chain

- Direct runtime dependency: `pyyaml` only.
- Optional extras — `real-model` (torch, transformers, accelerate), `legacy`, `gpu` (vllm,
  bitsandbytes), `viz` (matplotlib), `snapshot` (datasets, huggingface_hub), `dev` (pytest) —
  are imported lazily, so the offline path and CI do not install or import them.
- The `deploy` workflow publishes the static research dashboard to GitHub Pages; it does not
  publish secrets or run artifacts.

Dependencies are pinned to floors (`>=`) rather than exact versions. That is a deliberate
trade-off: exact pinning would make the offline CI unreproducible across environments, and
the project prefers bounds it can validate in CI. Review this choice before deploying in a
locked-down environment.
