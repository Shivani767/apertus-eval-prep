# Reproducing the active manuscript

The active paper is `main.tex` with `case_*.tex`, `tables/audited_*.tex`, `tables/numbers.tex`, and the referenced vector figure. Earlier `abstract.tex`, `intro.tex`, `results*.tex`, `ranking.tex`, `discussion.tex`, `setup.tex`, `framework.tex`, `repro.tex`, `appendix.tex` and non-audited tables are **superseded drafts**, retained rather than deleted. They contain stale claims and must not be submitted. The source bundle includes only active dependencies.

From this repository root:

```sh
make analyze PYTHON=.venv/bin/python
make paper PYTHON=.venv/bin/python
.venv/bin/python scripts/validate_paper.py
.venv/bin/python -m pytest -q
make reproduce-full PYTHON=.venv/bin/python
```

Use another installed interpreter via `PYTHON` where appropriate. Existing project dependencies must be installed; no new Python library was added. LaTeX compilation supports Tectonic or PDFLaTeX/BibTeX; only Tectonic has been tested here. `paper/analysis/analysis_environment.json` records the analysis environment, not the historical inference environment.

- `analyze`: raw validation, exact-count descriptive matrix, exact paired McNemar tests, stratified bootstrap, Holm corrections, generated tables/figures, deterministic regeneration check.
- `paper`: analysis plus an isolated clean-source build and asset-only `arxiv-source.tar.gz`. Does not submit anything. The local Tectonic package cache is used; this is not a clean-OS or arXiv-server test.
- `reproduce-full`: **dry-run experiment plan only**, not historical replay. The name does not imply exact reproducibility. Pin model/tokenizer revisions and resolve all setup gates before invoking the GPU runner without `--dry-run`. No inference is launched automatically.

Raw runs are never overwritten by paper reproduction. Selected successful registry rows define evidence; missing runs remain missing. No estimate of GPU hours/cost is available. Future runner/config infrastructure is existing work, not evidence of completed factorial experiments.

Validation compares generated analyses, every active numerical table and all generated vector figures against a temporary regeneration. It rejects non-finite numeric artifacts, incomplete pairing, duplicate IDs, mismatched labels/score summaries, missing inputs and unresolved citation keys. It does not prove semantic extraction correctness, inferential assumptions, licensing, arbitrary prose numbers or author identity. Those are manual gates in the claim and submission audits.
