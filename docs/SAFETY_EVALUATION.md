# Safety evaluation

The safety suite is responsible, sanitized, and suitable for a public repository. Fixtures use abstract scenarios and safe redirects; they do not provide actionable harmful instructions, operational misuse procedures, or real sensitive data.

The configurable taxonomy includes prompt injection, data leakage, unauthorized instruction override, unsafe tool use, harmful-content compliance, benign false refusal, privacy-sensitive output, unsupported high-stakes claims, misleading confidence, policy-bypass attempts, and retrieval-context manipulation.

Metrics expose attack success rate, category pass rate, safe refusal rate, benign false-refusal rate, high-severity failures, severity/category weighted risk, and per-category breakdowns. Weights are configuration, not hidden constants. The legacy `weighted_risk_score` is normalized by attack cases when attack cases exist; its denominator, numerator, and all-evaluated alternative are also reported. A zero is a measured zero only when evaluated cases exist; skipped adapter failures remain missing evidence and are counted separately.

```bash
PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-safety \
  --config configs/platform_safety.yaml --out runs/safety

# Expanded public-safe Phase 4 corpus, taxonomy, weights, and gate policy
PYTHONPATH=src .venv/bin/python -m apertus_eval_prep platform-safety \
  --config configs/platform_phase4_safety.yaml --out runs/phase4-safety
```

The expanded run writes `safety_report.md` and `safety_report.html` alongside the standard run artifacts, including `failure_fingerprint.json`. Use `--baseline-run <prior-run-directory>` (or `run.baseline_run` in YAML) for aligned safety comparison. `platform-report` can rebuild the generic escaped review report from the immutable run directory without rerunning the safety adapter.

Automated safety evaluation is not certification. High-impact releases should add human review, policy experts, privacy/security review, real abuse testing under controlled conditions, monitoring, and incident response.
