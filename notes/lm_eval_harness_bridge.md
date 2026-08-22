# lm-evaluation-harness bridge (design only)

This harness is **not** an lm-eval backend. Scores here are generative exact-match. lm-eval multiple-choice numbers are usually loglikelihood. Do not paste one table into the other.

This note is the first step toward an *optional* adapter. Nothing below is implemented.

## Chat-template modes

| this repo (`--chat-template`) | what is rendered | closest lm-eval / HF convention |
|---|---|---|
| `tokenizer` | `tokenizer.apply_chat_template(..., add_generation_prompt=True)` on the user string | Instruct models in lm-eval when `apply_chat_template: true` (EleutherAI harness) / HF `chat_template` on the tokenizer |
| `none` | raw user string, no special tokens | Base-model / completion-only tasks; lm-eval with chat template **off** |
| `mismatched` | Llama-3 wrap around a non-Llama tokenizer's user string | There is no first-class lm-eval flag for this. It is the train-vs-serve bug: engine default template ≠ `tokenizer.chat_template` |

vLLM in this repo is **completion mode** on the already-rendered string (`llm.generate`, not `llm.chat()`). That is the opposite of “let vLLM apply a second template.” An adapter must keep that contract or the HF vs vLLM compare is invalid.

## What an adapter would do (later)

1. Export a frozen slice (`data/official/*.jsonl` or `data/eval_set.jsonl`) as an lm-eval task YAML whose `doc_to_text` is the stored `prompt` stem.
2. Map `chat_template: tokenizer|none` onto lm-eval `apply_chat_template` / `fewshot_as_multiturn`.
3. Keep this repo's letter/number extractors as a *generation* metric, named separately from lm-eval's loglikelihood `acc`.
4. Refuse to compare a loglikelihood HellaSwag number to `results/runs/*hellaswag*` from this tree.

Until that adapter exists, the stated mapping is the table above. Replay stays `python -m apertus_eval_prep eval` / `sweep`.
