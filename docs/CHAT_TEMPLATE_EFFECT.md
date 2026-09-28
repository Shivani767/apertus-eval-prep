# The chat template: what it costs, already measured

**Status:** DERIVED from committed artifacts. **No new measurement** — every number below is
transcribed from two JSON files already in this repository, with the source cited.

**Why this document exists.** Four of the seven curated models score exactly `0.0000` on the
38-item core suite. The cause is a prompt-protocol defect: the `local_transformers` adapter
built the model input as `"{system}\n\n{user}"` and handed it to the tokenizer raw, so an
instruction-tuned model was served like a base model. `apply_chat_template` now exists
(`ead7db2`). But a fix with no evidence that it matters is an assertion, so this document
records the evidence that already existed: **the repository measured this exact contrast
before the typed platform did, on the legacy harness.**

## The two runs

`results/hf_tokenizer.json` and `results/hf_none.json` are identical in every setting except
the one knob:

| setting | value | source |
|---|---|---|
| model | `Qwen/Qwen2.5-0.5B-Instruct` | `manifest.settings.model_id` |
| revision | `null` (unpinned) | `manifest.settings.revision` |
| data | `data/eval_set.jsonl`, 28 items | `manifest.settings.data_path` |
| backend / device | `hf` / `mps` | `manifest.settings.backend`, `.device` |
| seed, max_new_tokens | `0`, `96` | `manifest.settings` |
| hardware | Apple MPS, no CUDA | `manifest.hardware` |
| **`chat_template`** | **`tokenizer`** vs **`none`** | `manifest.settings.chat_template` |

The `incomparability` block inside `hf_tokenizer.json` states the rule this satisfies:
*"only compare two runs when the manifest.settings block matches except the one knob you
changed."* Everything else is byte-identical, so this is the sanctioned one-knob contrast,
not a loose comparison.

## Result

| task | n | `tokenizer` correct | `none` correct | Δ items |
|---|---:|---:|---:|---:|
| `arc_easy` | 8 | **8** | 5 | −3 |
| `gsm8k` | 8 | 2 | 2 | 0 |
| `multilingual` | 8 | **7** | 5 | −2 |
| `template_canary` | 4 | 3 | 3 | 0 |
| **overall** | **28** | **20 (0.7143)** | **15 (0.5357)** | **−5** |

Removing the chat template costs **5 of 28 items, −17.9 percentage points** overall. This
reproduces the `71.4% → 53.6%` pair already quoted in the abstract, read straight out of the
committed files.

**The effect is not uniform, and that is the interesting part.** The template changes nothing
on `template_canary` (3/4 both) and nothing on `gsm8k` (2/8 both). The entire loss is on
`arc_easy` (−3) and `multilingual` (−2) — short-instruction, single-token-answer tasks. So the
defensible claim is not "apply the chat template" but:

> The benefit of a chat template is task-dependent. It is concentrated on short
> single-token-answer tasks and is **not** measurable on multi-step reasoning, where both
> protocols scored 2/8.

That is a narrower and more testable claim than a blanket recommendation, and it is the kind
of statement a reviewer will probe rather than accept.

## What this does and does not license

**Licenses.** The direction and rough magnitude of the protocol cost are already evidenced
in this repository, on a real model, with per-item artifacts. The chat-template fix is
therefore **not** an untested hypothesis — the harm it removes was measured before the fix
existed. This is why `results/colab_real_model/README.md` says the committed zeros
"understate every model" without needing to run anything new.

**Does not license a transfer.** The `−17.9pp` figure belongs to a **0.5B** model, a
**28-item** canary, on **Apple MPS**. The curated cohort is 1.5B–3B on a T4 with different
suites. Nothing here establishes that any specific model in that cohort would gain 17.9
points; it establishes the mechanism and its rough scale on one model. Any write-up must
carry both halves of that sentence.

**Not a safety or capability claim.** `gsm8k` is unchanged and `arc_easy` starts at 8/8, so
this is not a story about reasoning ability. It is a story about output format, which is
exactly the artefact documented in the curated results.

## Pending analyses

Three follow-ups are **not** in this document because they have not been run. They are
implemented in [`scripts/analyse_existing_evidence.py`](../scripts/analyse_existing_evidence.py),
which is **written but not executed**; nothing it produces may be quoted until it has run and
its output has been read.

1. **Paired item-level discordance** — which five items flipped, and whether the flips
   concentrate in `arc_easy` and `multilingual` as the aggregate table suggests. The per-item
   `correct` flags exist in both files; the script joins them by item id and applies an exact
   sign test to the discordant pairs.
2. **Factorial interaction decomposition** — the design is OFAT, so most factor pairs are
   expected to return `UNAVAILABLE` rather than a number. That is the honest result and
   would convert an admitted limitation into a measured one.
3. **Leave-one-model-out generalization** — hides one model and asks whether reliability
   estimated from the visible models describes the hidden one. Three models meet the minimum;
   the result is a low-power probe and must be labelled as such.

## Reproducing the numbers in this document

No code is required; the values are in the committed files:

```bash
python -c "
import json
for f in ('results/hf_tokenizer.json','results/hf_none.json'):
    d=json.load(open(f)); t=d['tasks']
    print(f, t['overall'], {k: t[k]['correct'] for k in t if k!='overall'})
"
```

See also [`HELDOUT_GENERALIZATION.md`](HELDOUT_GENERALIZATION.md) for the budget-curve
result and the rank-reversal finding from the same registry.
