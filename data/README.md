# Frozen evaluation slice

This file is the bench. Do not regenerate it from Hugging Face at runtime.
Anyone who clones this repo scores the same items.

| task | n | what it is | license / origin |
|---|---|---|---|
| `arc_easy` | 8 | Multiple-choice science (ARC-Easy style). Items are original restatements, not a dump of the ARC test file. | Inspired by Clark et al., 2018, AI2 ARC (CC-BY-SA). |
| `gsm8k` | 8 | Grade-school math with a numeric gold. Original items in the GSM8K format. | Format from Cobbe et al., 2021 (MIT). |
| `multilingual` | 10 | Same arithmetic style in EN / DE / FR / IT / HI (Swiss official languages + the existing Hindi pair). Frozen after the n=28 Mac/T4 canary runs; those JSON files still score 8 multilingual items. | Original to this repo. Format inspired by Shi et al., 2022 MGSM. |
| `template_canary` | 4 | Format-locked items. Accuracy is supposed to drop if the chat template is missing or wrong. | Original to this repo. |

Gold answers are stored as `gold`. Scoring is exact-match after the extractors in `scoring.py`.

`data/paraphrase_set.jsonl` is a separate frozen slice: 4 stems × 3 wordings (`orig` / `p1` / `p2`), same gold. It is **not** part of the n=800 paper matrix and has no committed scores.

Official 200-item slices (ARC-Easy, GSM8K, HellaSwag, MGSM) are a separate frozen tree: [`data/official/`](official/). See [`official/SOURCES.md`](official/SOURCES.md). Those numbers are still generative exact-match, not lm-eval.
