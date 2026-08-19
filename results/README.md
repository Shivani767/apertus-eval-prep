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
