# Research Readiness Report

Date: 2026-09-12. Test state at writing: **231 passed, 0 failed** (`pytest -q`, ~3s).

## 1. Implementation status

| Capability | Status | Where |
|---|---|---|
| Configuration-driven experiments, OFAT, registry, provenance | existed | `sweep.py`, `registry.py`, `result_schema.py` |
| Interaction studies (4 factor pairs, full/balanced designs) | **added** | `interaction.py`, `tests/test_interaction.py` |
| Guarded factorial variance decomposition (SS partition, omega², bootstrap CIs) | **strengthened** | `variance.py`, `tests/test_pathological.py` |
| Three-layer stability (score / ranking / decision reliability) | **strengthened** | `stability.py`, `ranking.py`, `heldout.py` |
| Held-out configuration reliability validation (ECE/Brier/log-loss/AUROC/coverage) | **added** | `heldout.py`, `tests/test_heldout.py` |
| Leave-one-model-out generalization (OOD reported, not predicted) | **added** | `heldout.py` |
| Adaptive strategies incl. Apertus-R; budget curves; replay metrics | **strengthened** | `adaptive.py`, `tests/test_budget_replay.py` |
| Failure taxonomy | existed | `failures.py` |
| Statistical methodology docs | existed + gap analysis added | `docs/STATISTICAL_METHODOLOGY*.md`, `docs/research_gap_analysis.md`, `docs/research_formulation.md` |

## 2. Experiment status

- End-to-end research chain (split → held-out validation → interaction design
  → budget curves → LOMO) demonstrated on **synthetic** data:
  `python scripts/research_smoke.py` → `reports/research_smoke/research_smoke.json`
  (labeled `data: synthetic`, validation only — NOT evidence).
- Real-model experiments: OFAT stability/fragility results exist under
  `reports/` and `results/registry_paper.jsonl`. Interaction factorial runs
  and real budget-curve studies are **not yet executed** (require GPU access);
  the design/analysis layer is ready and smoke-tested.

## 3. Test status

- 231 tests pass; new files: `test_interaction.py` (19),
  `test_budget_replay.py` (14), `test_research_integrity.py` (9),
  `test_pathological.py` (18, ties/NaN/missing/single-model/zero-variance/
  incomplete designs/opposite rankings).
- Methodological fix made during testing: pairwise decisions now EXCLUDE tied
  configs (previously ties were silently counted as losses, fabricating
  confident decisions on identical models). Two pre-existing tests updated to
  the corrected convention.

## 4. Statistical status

- ANOVA applied only to complete, balanced designs (guarded, never forced);
  omega² effect sizes; bootstrap CIs; documented refusal reasons.
- Calibration metrics (ECE, Brier, log loss, AUROC, CI coverage) implemented
  with empty/one-class edge cases returning `None`, never fabricated.
- Multiple-comparison handling and paired designs remain per
  `docs/STATISTICAL_METHODOLOGY.md`; no p-value-only conclusions.

## 5. Reproducibility status

- All stochastic stages seeded; per-budget derived seeds; determinism
  test-enforced. Provenance fields recorded on artifacts (see
  `docs/research_integrity_audit.md`). Smoke run reproducible:
  `python scripts/research_smoke.py --seed 0`.

## 6. Paper readiness

- NOT publication-ready. Missing: real factorial experiment results, real
  budget-curve results, registry-backed figures for RQ1–RQ5, LaTeX main.tex.
- `docs/research_formulation.md` (problem formalization),
  `docs/research_gap_analysis.md` (capability audit), and
  `paper/RELATED_WORK.md` exist as the writing backbone.

## 7. Remaining limitations / known weaknesses

1. No real-model interaction or budget experiments yet — RQ3–RQ5 are
   untested empirically.
2. Leave-one-model-out with few models is a low-power probe (labeled).
3. ERS validity bounded to evaluated configuration distributions.
4. Budget-curve saturation on synthetic smoke data is an artifact of the
   planted signal, not a finding.
5. Hardware/runtime factors are metadata-only (not yet measurable factors).

## 8. Reproduce

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/research_smoke.py --seed 0
```
