# The chat template: what it costs, already measured

**Status:** DERIVED from committed artifacts. **No new measurement** — the aggregate table
is transcribed from two JSON files already in this repository, and the item-level table is
produced by [`scripts/analyse_existing_evidence.py`](../scripts/analyse_existing_evidence.py)
from those same files' per-item records. Sources are cited throughout.

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

## Item-level evidence

The aggregate table hides the most informative part. Joining the per-item `correct` flags
of both runs (`scripts/analyse_existing_evidence.py`, output committed under
`reports/existing_evidence/`) gives 28 shared items, 0 unmatched, and **7 discordant items**:

| task | n | templated only | none only | both right | both wrong | net |
|---|---:|---:|---:|---:|---:|---:|
| `arc_easy` | 8 | **3** | 0 | 5 | 0 | +3 |
| `gsm8k` | 8 | **0** | 0 | 2 | 6 | 0 |
| `multilingual` | 8 | **2** | 0 | 5 | 1 | +2 |
| `template_canary` | 4 | 1 | **1** | 2 | 0 | 0 |
| **total** | **28** | **6** | **1** | 14 | 7 | **+5** |

**Exact sign test on the discordant pairs: p = 0.125** (6 versus 1 of 7 discordant items).

Three things follow, and the third is the reason this is not a bigger result than it looks:

1. **`gsm8k` has zero discordant items.** Not "the template did not help enough" — it changed
   *nothing* on multi-step reasoning. Both protocols scored 2/8.
2. **`template_canary` churned in both directions**, one item each way, netting zero. The
   template was not silently *correct* there; it was not silently *worse* either. That is
   noise on four items, and it should not be read as evidence in either direction.
3. **p = 0.125 is not significant at 0.05.** With seven discordant items on a 28-item canary,
   the 5-item advantage is **directional evidence, not a precise magnitude**. The honest
   statement is that the effect is concentrated in short single-token-answer tasks and is
   absent on multi-step reasoning — not that the template is worth 17.9 points.

The whole net effect is `arc_easy` (+3) and `multilingual` (+2). Neither is a reasoning
result: both are short-prompt, single-token-answer tasks where the failure mode is the model
continuing the passage instead of replying.

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

## The other two analyses

Both ran; both results are in `reports/existing_evidence/analysis.md`.

**Factorial interaction decomposition: UNAVAILABLE, and that is the result.** The only
crossed design the registry can express is `model_id × factor`, and it is neither complete
nor balanced, because an OFAT design never varies two factors together within a model. The
decomposition returns `UNAVAILABLE` with that reason rather than forcing an ANOVA. The
`paper/case_limits.tex` limitation — *"OFAT design cannot detect factor interactions"* — is
now a **measured** limitation rather than an admitted one. Detecting it would require a
balanced factorial run, which does not exist in this repository.

**Leave-one-model-out: reported, low power.** With three models each fold leaves one visible
pair, and in-distribution pairwise decision accuracy is 1.000 at every budget tested. The
hidden model's configuration sensitivity is 0.044–0.050 (std of its accuracy across the 11
configurations). With one pair per fold this is **one comparison per fold**: it is a probe
that the pairwise ordering survives hiding a model, not evidence of generalization, and it is
labelled as such in the output.

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
