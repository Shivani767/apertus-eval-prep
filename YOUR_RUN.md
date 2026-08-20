# Your run sequence (do this in order)

The repo on disk is the scaffold. It becomes an artefact only after **you** produce JSON that a stranger can open.

Estimated time: smoke 15–20 min (download + 4 items). Full Mac eval ~30–60 min per config × 3 configs. Colab vLLM ~20 min on a T4.

## 0. One-time

Do not create a virtualenv inside a folder whose path contains `:`.
`python -m venv` will refuse. Clone or copy to a path such as `~/apertus-eval-prep`.

```bash
cd ~/apertus-eval-prep
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
pytest -q
```

Create the GitHub repo **public**, named `apertus-eval-prep`, under `Shivani767`. Push this folder. Until it is public, Zürich cannot open it at 11pm.

## 1. Mac smoke (today)

```bash
python -m apertus_eval_prep eval --config configs/smoke.yaml --out results/smoke.json
```

Check: `results/smoke.json` has `manifest.hardware`, `manifest.settings.chat_template`, and four `items`. If this fails, stop and fix before the full run.

## 2. Dump prompts (today, 2 minutes after tokenizer download)

```bash
python -m apertus_eval_prep dump-prompts --config configs/default.yaml --out results/prompts_tokenizer.txt
python -m apertus_eval_prep dump-prompts --config configs/no_template.yaml --out results/prompts_none.txt
python -m apertus_eval_prep dump-prompts --config configs/mismatched.yaml --out results/prompts_mismatched.txt
```

Open the three files. You should see ChatML (`<|im_start|>`) in tokenizer mode, raw English in none, and `<|begin_of_text|>` Llama-3 tokens in mismatched. That screenshot-in-text is the train vs serve explanation.

## 3. Three Mac evals (this is Project A)

```bash
python -m apertus_eval_prep eval --config configs/default.yaml --out results/hf_tokenizer.json
python -m apertus_eval_prep eval --config configs/no_template.yaml --out results/hf_none.json
python -m apertus_eval_prep eval --config configs/mismatched.yaml --out results/hf_mismatched.json
```

Leave them running. Do not edit the JSON.

```bash
python -m apertus_eval_prep compare results/hf_tokenizer.json results/hf_none.json --out results/compare_template.md
python -m apertus_eval_prep compare results/hf_tokenizer.json results/hf_mismatched.json --out results/compare_mismatch.md
```

## 4. Colab vLLM (Project B)

1. Upload this repo or `git clone` the public GitHub URL.
2. Open `notebooks/colab_vllm.ipynb`.
3. Runtime → GPU (T4).
4. Run all. Download `vllm_tokenizer.json` and `compare_backend.md` into `results/`.

If Colab will not install vLLM, still ship the Mac template ablation. Add one honest sentence: vLLM comparison pending on a CUDA box. Do not invent vLLM numbers.

## 5. Commit the numbers

`.gitignore` ignores `results/*.json` except the schema example. When a run is real, force-add it:

```bash
git add -f results/hf_tokenizer.json results/hf_none.json results/hf_mismatched.json \
  results/vllm_tokenizer.json results/compare_template.md results/compare_mismatch.md \
  results/compare_backend.md results/prompts_tokenizer.txt results/prompts_none.txt \
  results/prompts_mismatched.txt
git commit -m "Add measured HF vs template/vLLM runs"
git push
```

Commit **after** the code is already on `main`, so `manifest.git_commit` points at the harness they cloned.

## 6. Sentence for the letter

After the files exist, this is true:

> Public harness: github.com/Shivani767/apertus-eval-prep — frozen ARC/GSM8K/multilingual slice; Hugging Face generate vs vLLM; chat-template on / off / mismatched; TTFT p95 in the same JSON. I have not used Slurm on Alps; this is the same job at smaller scale.

If vLLM is not done, drop “vs vLLM” until it is. Do not keep the phrase.

## 7. Ranking stability (Colab T4)

Smoke (n=4) is already on GitHub. The **paper matrix** is `configs/experiments/stability.yaml`.

1. Open [`notebooks/colab_stability.ipynb`](notebooks/colab_stability.ipynb). Runtime → **T4**.
2. First cell `git pull`s, then run the **paper matrix** cell (`--registry results/registry_paper.jsonl`). 34 cells × 800 items; hours.
3. After each `[800/800]`, download `results/registry_paper.jsonl` and the new `results/runs/*.json` from the Files sidebar. Do not start another notebook cell while the sweep is running.
4. Copy those files into this clone. Next session, upload them into the Colab `results/` folder, then rerun the same sweep cell (or `--only-model`). Finished hashes skip.
5. Run the report/zip cell only when this runtime actually has `results/runs`. Unpack into this clone. Commit. Do not type numbers.

`--profile t4` skips 7B fp16 / int8 / vLLM. Use `--profile a10` on an A10.

## Stop conditions

- Do not tune prompts until the 0.5B model “looks good.” The canary is allowed to fail.
- Do not switch the model to Apertus-8B on a Mac.
- Do not paste Josh-internal evals into this repo.
