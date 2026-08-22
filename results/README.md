Commit real JSON from `apertus-eval-prep eval` here after you run it.

Suggested names (match the configs):

| file | command |
|---|---|
| `hf_tokenizer.json` | `--config configs/default.yaml` |
| `hf_none.json` | `--config configs/no_template.yaml` |
| `hf_mismatched.json` | `--config configs/mismatched.yaml` |
| `vllm_tokenizer.json` | Colab: `--config configs/vllm.yaml` |
| `compare_template.md` | `compare results/hf_tokenizer.json results/hf_none.json` |
| `compare_backend.md` | `compare results/hf_tokenizer.json results/vllm_tokenizer.json` |
| `prompts_tokenizer.txt` | `dump-prompts --config configs/default.yaml` |

Do not edit numbers by hand. If a run is dirty (uncommitted code), the manifest `git_dirty` field will say so — commit the harness first, then re-run.

Ranking study (Colab): `results/runs/<run_id>.json` plus [`registry.jsonl`](registry.jsonl) (n=4 smoke) or [`registry_paper.jsonl`](registry_paper.jsonl) (800-item matrix). Controls in git: SmolLM2 `24ffe98d9250761d` (318/800), Qwen-3B `cff017903a47abb9` (515/800), Phi-3.5 `31791224954ba45c` (536/800). SmolLM2 prompt OFAT: concise `a0852ca6fc3e5c08` (186/800), 5shot `b6968af4b73708f7` (274/800).

Free Colab resets wipe `/content`. After each finished cell, download the registry **and** the matching run JSON; copy them here before the VM dies.
