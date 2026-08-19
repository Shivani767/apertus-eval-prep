# What makes two scores not comparable

A number in `results/*.json` is only meaningful next to its `manifest.settings` and `manifest.hardware` blocks. Change any of the following and you are no longer looking at the same measurement:

1. **Chat template.** `tokenizer` vs `none` vs `mismatched`. This is the train-vs-serve bug. Apertus serving commands pass `--chat-template-content-format string` for a reason. If the tokenizer and the engine disagree, scores move.
2. **Tokenizer identity.** `model_id` and `tokenizer_id` and `revision`. A different tokenizer is a different prompt, even if the UTF-8 text looks the same.
3. **Backend.** Hugging Face `generate` vs vLLM. [swiss-ai/evals-post-train](https://github.com/swiss-ai/evals-post-train) already warns that generation tasks (GSM8K-style) can differ slightly between HF and vLLM. Compare backends only when the rendered prompt strings are identical (this harness does that on purpose: vLLM is called in completion mode, not `llm.chat()`).
4. **Decoding.** This repo is greedy (`do_sample=False`, temperature 0). Sampling, different `max_new_tokens`, or extra stop strings make a new experiment.
5. **Hardware and dtype.** CPU float32, Apple MPS float16, and CUDA bfloat16 are not the same numeric pipeline. Report them; do not hide them.
6. **Item slice.** Scores here are on `data/eval_set.jsonl`, 28 frozen items. They are not MMLU, not Alps, and not a model card headline.

The `compare` command prints which of those knobs actually changed. If more than one changed, do not tell a story about a single cause.
