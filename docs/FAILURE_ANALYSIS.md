# Failure analysis

Failure records preserve a failure ID, run/episode ID, category, severity, input hash, sanitized input excerpt when allowed, an output artifact reference, conditions, trace reference, reproduction command, human-review status, and tags. Runtime failures are labeled as infrastructure failures and are not treated as unsafe model behavior.

The fingerprint groups failures by category, identifies safety-critical and stable failures, detects examples observed under multiple conditions, and recommends an investigation priority. The goal is actionable diagnosis rather than a single aggregate score.


For a Phase 8 study, use `platform-study-analyze` to carry these fingerprints into the study summary and export sanitized candidates for review. Human-review status is independent of model evidence: a completed review linked to a synthetic run remains synthetic, and a template remains unreviewed. Investigation priorities describe observed patterns, not causes. See `docs/FAILURE_ANALYSIS.md` and `docs/HUMAN_REVIEW_PROTOCOL.md`.

Use `platform-compare` to inspect baseline/candidate failure changes and `release.failures.failure_fingerprint` for programmatic aggregation. Normal platform runs persist the derived `failure_fingerprint.json`; use `platform-fingerprint` to rebuild it without rerunning the model. Keep raw examples out of public artifacts when retention is disabled. Representative examples are sanitized and reviewed for representativeness and privacy.
