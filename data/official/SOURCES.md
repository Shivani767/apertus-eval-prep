# Official frozen slices

These JSONL files are the bench. Eval does not re-download them.
Regenerate with `pip install -e ".[snapshot]" && python scripts/snapshot_benchmarks.py --force` and commit.

Selection: shuffle with seed `0` (eval) / `1` (few-shot),
then take first 200 eval items and 5 few-shot items per task.
MGSM is split across EN/DE/FR. MGSM few-shot comes from the official train
split (8 exemplars/language), not from the scored test items.

Protocol: **generative exact-match** (letter or last number). This is not
lm-eval loglikelihood HellaSwag/ARC. Do not quote these numbers as leaderboard scores.

| task | file | Hugging Face id | split | n | license | hub sha |
|---|---|---|---|---|---|---|
| `arc_easy` | `arc_easy.jsonl` | `allenai/ai2_arc` | test | 200 | CC-BY-SA-4.0 | `210d026faf9955653af8916fad021475a3f00453` |
| `gsm8k` | `gsm8k.jsonl` | `openai/gsm8k` | test | 200 | MIT | `740312add88f781978c0658806c59bc2815b9866` |
| `hellaswag` | `hellaswag.jsonl` | `Rowan/hellaswag` | validation | 200 | MIT | `218ec52e09a7e7462a5400043bb9a69a41d06b76` |
| `mgsm` | `mgsm.jsonl` | `juletxara/mgsm` | test | 200 | MIT | `b2f13d426afe3be8d69a7e739b36724db8b66bbc` |

Combined files: `eval_set.jsonl` (all eval items) and `fewshot.jsonl`.

ARC-Easy: Clark et al., 2018, AI2. GSM8K: Cobbe et al., 2021.
HellaSwag: Zellers et al., 2019. MGSM: Shi et al., 2022.
