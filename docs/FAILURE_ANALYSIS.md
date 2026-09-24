# Failure analysis

Failure records preserve a failure ID, run/episode ID, category, severity, input hash, sanitized input excerpt when allowed, an output artifact reference, conditions, trace reference, reproduction command, human-review status, and tags. Runtime failures are labeled as infrastructure failures and are not treated as unsafe model behavior.

The fingerprint groups failures by category, identifies safety-critical and stable failures, detects examples observed under multiple conditions, and recommends an investigation priority. The goal is actionable diagnosis rather than a single aggregate score.

Use `platform-compare` to inspect baseline/candidate failure changes and `release.failures.failure_fingerprint` for programmatic aggregation. Normal platform runs persist the derived `failure_fingerprint.json`; use `platform-fingerprint` to rebuild it without rerunning the model. Keep raw examples out of public artifacts when retention is disabled. Representative examples are sanitized and reviewed for representativeness and privacy.
