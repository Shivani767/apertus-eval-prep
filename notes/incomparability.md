# What makes two scores not comparable

A number in `results/*.json` is only meaningful next to its `manifest.settings` and `manifest.hardware` blocks. Change any of the following and you are no longer looking at the same measurement:

1. **Chat template.** `tokenizer` vs `none` vs `mismatched`. This is the train-vs-serve bug. Apertus serving commands pass `--chat-template-content-format string` for a reason. If the tokenizer and the engine disagree, scores move.
2. **Tokenizer identity.** `model_id` and `tokenizer_id` and `revision`. A different tokenizer is a different prompt, even if the UTF-8 text looks the same.
3. **Backend.** Hugging Face `generate` vs vLLM. [swiss-ai/evals-post-train](https://github.com/swiss-ai/evals-post-train) already warns that generation tasks (GSM8K-style) can differ slightly between HF and vLLM. Compare backends only when the rendered prompt strings are identical (this harness does that on purpose: vLLM is called in completion mode, not `llm.chat()`).
4. **Decoding.** Default is greedy (`temperature: 0`). A sampled arm (`temperature: 0.7`) and extra seeds are a different experiment. Different `max_new_tokens` or stop strings also make a new experiment.
5. **Prompt variant.** `prompt_id` (`default` / `concise` / `5shot`) changes the user string before the chat template. Official slices store stems only; the 28-item canary already includes instructions and leaves `prompt_id` unset.
6. **Quantization.** `none` / `int8` / `int4` (HF + bitsandbytes, CUDA/Colab only). Do not cross quantization with vLLM in this harness. An int4 T4 row is not the control fp16 row, even if `model_id` matches.
7. **Hardware and dtype, per cell.** CPU float32, Apple MPS float16, and CUDA bfloat16/float16 are not the same numeric pipeline. The paper matrix is Colab Tesla T4; the template canary is Mac MPS. Do not pool them. Two T4 cells can still be incomparable if one manifest says Python 3.12 and another 3.13, or if `dtype: auto` resolved differently — read `manifest.hardware` on **that** JSON, not a table caption.
8. **Item slice.** The template canary is `data/eval_set.jsonl` (now 30 items: 28 plus Italian `ml_it_*`). Ranking tables use `data/official/*.jsonl` (n=800). They are still not a model card headline. Generative exact-match is not lm-eval loglikelihood. Adding languages to the canary after a committed n=28 run does not rewrite Experiment 1–2.
9. **Prompt paraphrase** (when that factor exists). `paraphrase_id` `orig` / `p1` / `p2` is a different user string on the same gold. It is not `prompt_id` (instruction wrapper) and not a new task. Official n=800 stems have no paraphrase variants; do not run `paraphrase_id` against `data/official/eval_set.jsonl`.

The `compare` command prints which of those knobs actually changed. If more than one changed, do not tell a story about a single cause.
