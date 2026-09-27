# Security Policy

## Reporting a vulnerability

**Do not open a public issue for a security vulnerability.** Use GitHub's private
reporting: [Security → Report a vulnerability](https://github.com/Shivani767/apertus-eval-prep/security/advisories/new).

Please include the affected version or commit, a description of the issue, reproduction
steps, and the impact you believe it has. You can expect an acknowledgement within a few
days. Fix timing will be discussed with you once the scope is understood.

If private reporting is unavailable to you, open an issue that describes the *category* of
the problem without exploit details and ask for a private channel.

## Do not post these in public issues, pull requests, or commits

This repository evaluates models and can retain model outputs. Treat every artifact as
potentially sensitive:

- API keys, access tokens, passwords, private keys, or `.env` contents.
- Private datasets, licensed corpora, or internal documents.
- Sensitive prompts, customer data, or personal data of any kind.
- **Unredacted run logs or `raw_outputs.jsonl` files** that contain real model responses.
- Hugging Face tokens, including ones you believe are expired or revoked.

A token that has ever been pasted into a chat, an issue, or a commit should be treated as
compromised and **revoked**, not deleted. Deleting a message does not unpublish it.

`tests/test_no_secrets_committed.py` runs in CI and fails the build if a credential-shaped
string is committed. It is a safety net, not a substitute for care.

## Redaction is a reduction, not a guarantee

The platform applies pattern-based redaction (`apertus_eval_prep.utils.pii`) to logs,
artifacts, and reports. This detects **common shapes** — email addresses, credit-card-like
digits, phone numbers, and credential patterns such as `sk-`, `hf_`, and `ghp_` prefixes.

Pattern matching **cannot prove a payload is anonymous.** It will not detect a secret in an
unfamiliar format, a name in free text, or content whose meaning only a reader understands.
Treat redaction as a first filter that lowers risk, never as a guarantee of anonymization.

Where a run must be published, review the actual output before committing it.

## Raw-output retention is a real risk

`raw_outputs.jsonl` preserves what a model actually said. That is what makes the research
reproducible, and it is also the most likely place for sensitive content to appear — a
model will echo whatever it was given, and a prompt can contain personal data.

Mitigations available in the platform:

- `platform-export-review` emits a **sanitized** review package suitable for sharing.
- Reports and logs are redacted before rendering.
- Scoped tasks and safe fixtures keep sensitive content out of runs in the first place.

Before committing any run directory, read it.

## Responsible use of safety-test artifacts

The safety suite (`platform-safety`) and the curated safety artifacts are **defensive
research material**.

- Use them to evaluate and improve systems you are authorized to test.
- Do not republish generated harmful content as an illustration, a dataset, or marketing
  material.
- The suite is a red-team evaluation over a declared taxonomy. It is **not** a safety
  certification, and a passing result does not mean a system is safe.
- Keep safety artifacts out of production prompts and out of any prompt set that reaches an
  end user without review.

## Security posture of the code itself

- The base install has **one runtime dependency** (`pyyaml`). GPU runtimes are optional
  extras imported lazily, so the offline path has a small attack surface.
- CI runs offline, CPU-only, with no API keys, no GPU, and no model downloads.
- HTML reports escape dynamic content before rendering.
- The framework performs **no network calls** of its own. Real-model adapters reach the
  Hugging Face Hub, and the gated-model preflight authenticates with `whoami` and downloads
  a single small file to verify access.
- `hub_auth` never logs, prints, or persists a token; it publishes a validated token into
  the process environment so a child process can inherit it.

See [`docs/SECURITY_AND_PRIVACY.md`](docs/SECURITY_AND_PRIVACY.md) for the full privacy
posture and [`docs/FAQ.md`](docs/FAQ.md) for related questions.
