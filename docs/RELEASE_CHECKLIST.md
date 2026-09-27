# Release Checklist

Run this before tagging a release. Each item states how to verify it, not just that it
should be done. Items marked **release decision** are the maintainer's call and cannot be
automated.

## 1. Tests and validation

- [ ] `python -m pytest -q` passes on a clean checkout, with no network access.
- [ ] `python -m compileall -q src` succeeds.
- [ ] Offline smoke run completes and writes artifacts:
      `python -m apertus_eval_prep platform-run --config configs/platform_smoke.yaml --out runs/ci-smoke`
- [ ] `platform-report`, `platform-fingerprint`, `platform-gate`, `platform-ingest-runs`,
      `platform-select`, `platform-export-review`, `platform-ingest-review`, and
      `platform-study-analyze` each run against fixtures.
- [ ] Every `platform-*` and legacy command responds to `--help` without error.
- [ ] YAML and JSON configs parse; notebooks are valid JSON and their code cells parse.
- [ ] `git diff --check` reports no whitespace errors.
- [ ] The mock path imports none of `torch`, `transformers`, `vllm`, `accelerate`.

## 2. Evidence and claim boundaries

- [ ] Every new claim in README/docs is traceable to an evidence mode.
- [ ] No document describes mock or synthetic output as a benchmark result.
- [ ] No document describes a real model as executed unless preserved artifacts exist in
      `results/colab_real_model/<model>/`.
- [ ] No document claims human validation unless completed, linked review artifacts exist.
- [ ] Mock latency is never described as hardware performance.
- [ ] Fixture cost is never described as provider pricing.
- [ ] Release gates are never described as production approval.
- [ ] Safety results are never described as a safety certification.
- [ ] Findings are scoped to their recorded configuration, not generalized.
- [ ] `MOCK`, `SYNTHETIC`, `LOCAL_REAL_MODEL`, `EXTERNAL_PROVIDER`, and `UNKNOWN` labels are
      used consistently.
- [ ] Reports still render missing evidence as unavailable, never as zero.

## 3. Security and privacy

- [ ] Secret scan over tracked files is clean (locations and categories only; never print
      suspected values).
- [ ] `tests/test_no_secrets_committed.py` passes.
- [ ] No `.env`, token file, private key, or credential file is tracked.
- [ ] No model weights, caches, or large unreviewed run outputs are committed.
- [ ] New artifacts were read before being committed — `raw_outputs.jsonl` in particular.
- [ ] `SECURITY.md` and `docs/SECURITY_AND_PRIVACY.md` reflect current behaviour.

## 4. Documentation

- [ ] `README.md` positioning, capability table, quickstart, and limitations are current.
- [ ] `docs/CLI_REFERENCE.md` matches the live `--help` output for every command.
- [ ] Every config path referenced in documentation exists in the repository.
- [ ] Placeholders are visibly marked as placeholders (for example
      `REPLACE_WITH_INVESTIGATOR`).
- [ ] Stale, duplicate, or obsolete documentation references are removed.
- [ ] Internal cross-links resolve.

## 5. Dependencies and packaging

- [ ] `pyproject.toml` version matches the tag.
- [ ] Direct dependencies reviewed; unused ones removed only after confirming they are
      genuinely unused.
- [ ] Optional extras still justified, and each one's purpose documented.
- [ ] `python -m build` (or equivalent) produces a wheel and sdist that install cleanly in a
      fresh environment.
- [ ] Base install does not pull GPU runtimes.

## 6. Release identity — **release decision**

- [ ] License is chosen and present. This repository uses **Apache-2.0**; confirm that is
      still the intent. (Had no license existed, the choice would belong to the owner, not to
      a release checklist.)
- [ ] `CITATION.cff` contains only verified metadata — **no placeholder DOI**. Remove the
      `doi` field entirely until a real deposit exists; do not ship `10.5281/zenodo.TODO`.
- [ ] `CHANGELOG.md` has a dated section summarizing the release.
- [ ] Version tag created and pushed (for example `v1.0.0`).
- [ ] GitHub release notes published, describing **software** capabilities rather than
      model results.

## 7. Repository hygiene

- [ ] No stray files at the repository root; scripts live in `scripts/`, tests in `tests/`.
- [ ] `.gitignore` covers environments, caches, build artifacts, runs, model caches, notebook
      checkpoints, `.env`, credentials, and coverage output.
- [ ] `.gitignore` does **not** ignore source, configs, tests, fixtures, docs, curated safe
      reports, or notebooks.
- [ ] CI workflow runs offline, CPU-only, with no secrets required.

## 8. Optional real-model study evidence

- [ ] If the release includes new real-model evidence: each model directory has a
      `summary.md`, a recorded revision, and a recorded evidence mode.
- [ ] Failed attempts are recorded under `results/colab_failed_runs/`, not mixed into
      `results/colab_real_model/`.
- [ ] The cross-model comparison was regenerated after any change to the model set.
- [ ] Pinned revisions where available; unpinned `main` runs are flagged as such.

## 9. Optional human-review evidence

- [ ] If the release claims human review: completed, linked annotation artifacts exist and
      are committed.
- [ ] Otherwise, the release makes no human-validation claim anywhere.
- [ ] Agreement is described as annotator consistency, not correctness or safety.

## 10. Final review

- [ ] Known limitations reviewed and still accurate.
- [ ] `docs/FINAL_AUDIT.md` and `docs/FINAL_RELEASE_REPORT.md` match the shipped state.
- [ ] A second person has read the README top to bottom as if they had never seen the
      project.
