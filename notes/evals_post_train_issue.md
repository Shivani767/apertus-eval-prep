# Draft only — do not open until reviewed

Proposed GitHub issue on [swiss-ai/evals-post-train](https://github.com/swiss-ai/evals-post-train).
Not filed. Edit freely; numbers below are copied from committed JSON in [apertus-eval-prep](https://github.com/Shivani767/apertus-eval-prep).

---

**Title:** Generative exact-match moves when the chat template or HF/vLLM backend changes (replayable canary)

**Body:**

`evals-post-train` already notes that GSM8K-style *generation* can differ slightly between Hugging Face `generate` and vLLM. I froze a 28-item canary and measured two single-knob ablations so the warning has a replayable JSON pair.

**1. Chat template (Mac, HF generate only, same weights, same 28 items)**

| file | `chat_template` | overall |
|---|---|---|
| [`results/hf_tokenizer.json`](https://github.com/Shivani767/apertus-eval-prep/blob/master/results/hf_tokenizer.json) | tokenizer | 20/28 (71.4%) |
| [`results/hf_none.json`](https://github.com/Shivani767/apertus-eval-prep/blob/master/results/hf_none.json) | none | 15/28 (53.6%) |
| [`results/hf_mismatched.json`](https://github.com/Shivani767/apertus-eval-prep/blob/master/results/hf_mismatched.json) | Llama-3 wrap on Qwen | 12/28 (42.9%) |

GSM8K stayed 2/8 in all three. ARC and the format canary moved. Write-up: [`notes/findings.md`](https://github.com/Shivani767/apertus-eval-prep/blob/master/notes/findings.md) Experiment 1.

**2. Backend (Colab T4, template fixed to tokenizer, same rendered completion strings)**

Source table: [`results/compare_backend.md`](https://github.com/Shivani767/apertus-eval-prep/blob/master/results/compare_backend.md)

| file | backend | overall |
|---|---|---|
| Colab HF (see compare file; `hf_tokenizer_colab.json` is not in the tree) | hf | 20/28 (71.4%) |
| [`results/vllm_tokenizer.json`](https://github.com/Shivani767/apertus-eval-prep/blob/master/results/vllm_tokenizer.json) | vllm | 18/28 (64.3%) |

The −7.1 pp is multilingual (7/8 → 4/8), not ARC. One GSM8K item flipped (n=8). vLLM TTFT fields are empty in that JSON — do not invent a latency comparison.

**Ask.** Is the intended evals-post-train contract “same rendered string, completion mode, no second `llm.chat()` wrap”? If yes, a one-line pointer in the generation-task note to a frozen canary would make the HF/vLLM warning checkable. Happy to open a PR that only adds a link.

Harness: https://github.com/Shivani767/apertus-eval-prep
