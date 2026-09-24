# Citation and novelty audit

Checked against primary landing-page metadata in this revision (2026-09-16):

| Key | Primary source | Result |
|---|---|---|
| sclar2024quantifying | https://arxiv.org/abs/2310.11324 | Title/authors and ICLR 2024 confirmed. Prior art for format spread and model-relative sensitivity. |
| mizrahi2024state | https://aclanthology.org/2024.tacl-1.52/ | Title, six authors, TACL volume 12, pages 933–949, 2024 confirmed. Direct prior art for relative multi-prompt evaluation. |
| biderman2024lessons | https://arxiv.org/abs/2405.14782 | Listed author prefix, title and 2024 initial submission confirmed. |
| miller2024adding | https://arxiv.org/abs/2411.00640 | Evan Miller, title, 2024 confirmed. |
| liang2022holistic | https://arxiv.org/abs/2211.09110 | HELM title/author prefix/initial year checked; corrected Eric Zelikman. Cites initial arXiv version, not an invented venue. |
| srivastava2022beyond | https://arxiv.org/abs/2206.04615 | BIG-bench title/author prefix/initial year checked; corrected Abhishek Rao and Adrià Garriga-Alonso. |
| clark2018think | https://arxiv.org/abs/1803.05457 | ARC title/authors/year confirmed; preprint entry, not peer-reviewed proceedings claim. |
| cobbe2021training | https://arxiv.org/abs/2110.14168 | Replaced incorrect inherited author list with primary source's twelve authors. |
| zellers2019hellaswag | https://aclanthology.org/P19-1472/ | Title, authors, ACL 2019 and pages confirmed. |
| shi2022language | https://arxiv.org/abs/2210.03057 | Replaced incorrect inherited author list with primary source's twelve authors. |
| mcnemar1947note | https://api.crossref.org/works/10.1007/BF02295996 | Publisher-deposited Crossref metadata checked on 2026-09-16: Quinn McNemar; title confirmed; Psychometrika 12(2), 153–157, print publication June 1947. The 2025 online date is not the original publication year. |
| wilson1927probable | https://api.crossref.org/works/10.1080/01621459.1927.10502953 | Publisher-deposited Crossref metadata checked on 2026-09-16: Edwin B. Wilson; title confirmed; Journal of the American Statistical Association 22(158), 209–212, June 1927. Publisher landing-page access was blocked, but deposited bibliographic metadata was accessible. |
| holm1979simple | https://www.jstor.org/stable/4615733 | Access challenge; inherited metadata still needs final primary-source verification. |

No external numerical results are copied into the manuscript. Long author lists use BibTeX `and others`, not invented complete lists. Unused historical bibliography entries are not certified and should be pruned or checked before submission. The checklist does NOT mark all bibliographic metadata verified.

## Positioning / remaining breadth review

- Prompt sensitivity and model ordering changes are established prior art, not a first/novel discovery here.
- HELM, BIG-bench and lm-evaluation-harness already provide evaluation infrastructure; our contribution is the audited case study and raw-output analysis.
- MMLU, Open LLM Leaderboard and Dynabench are relevant broader evaluation context, not evaluated datasets or baselines in this artifact. A broader literature synthesis is still needed before any general leaderboard claim.
- Quantization, backend numerical differences and stochastic decoding have substantial existing literature; no methodological novelty or general causal effect is claimed here.
- ERS is unvalidated tooling, omitted from central empirical claims.

Status: **NEEDS REVISION** for remaining metadata and broader related-work review; no priority claim.
