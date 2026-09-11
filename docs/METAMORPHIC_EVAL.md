# Metamorphic evaluation & the EvalFrag benchmark (Phases 7–8)

## Why

If a benchmark score changes when we *rephrase* a question, add a neutral
instruction, or normalize whitespace, then part of the "score" is an artifact
of the evaluation surface, not the model+task. Metamorphic evaluation makes
these controlled perturbations first-class, labelled, and auditable.

Every transformation below is **explicitly labelled** with:
- `family` (paraphrase / formatting / instruction_prefix / suffix_answer_request)
- `expected_invariance` — a DESIGNED property of the transform, never a
  measured claim. "Designed inert" means: if a model's correctness moves under
  this transform, that movement is fragility *evidence*, because the change was
  constructed to be task-preserving.

We never claim semantic equivalence beyond construction: the transforms only
touch text (prefix/suffix/normalization) or use the hand-checked
`data/paraphrase_set.jsonl` wordings; gold/task/language are copied unchanged
and validated by `validate_preservation`.

## Module: `src/apertus_eval_prep/metamorphic.py`

- `transform_formatting / transform_prefix / transform_suffix` — rule-based,
  deterministic, task-preserving by construction.
- `Perturbation` dataclass: `perturbation_id, source_item_id, task, language,
  gold, family, original_prompt, perturbed_prompt, expected_invariance,
  labels, provenance`.
- `load_paraphrase_groups(path)` — reads the existing committed
  `data/paraphrase_set.jsonl` (4 stems × orig/p1/p2) into labelled
  `paraphrase` perturbations (8 rows).
- `build_evalfrag_rows(items, families, max_per_family)` — deterministic small
  seed from frozen `data/official/*` items.
- `to_jsonl` / `observed_summary` — stable JSONL schema with `observed: null`
  (PENDING) until a real run attaches correctness; summaries never fabricate
  evidence (`status: PENDING`, `invariant_rate: None` with zero evidence).

## Data: `data/evalfrag/evalfrag_seed.jsonl` (PENDING)

12 rows = 4 task families (arc_easy knowledge, gsm8k maths, hellaswag
reasoning, mgsm multilingual) × 3 perturbation families (formatting,
instruction_prefix, suffix_answer_request). Golds are copied verbatim from the
frozen official items (`source_item_id` gives the provenance chain). All
`observed` values are `null`: no score is attached until an actual evaluation
run records correctness against these exact perturbed prompts.

Code/safety/hallucination perturbation families are **UNAVAILABLE** for now:
the frozen official eval set does not contain those task families, and we do
not invent benchmark content.

Regenerate (deterministic):

```bash
python scripts/build_evalfrag_seed.py
```

## How to run the perturbations

Standard harness: a perturbed prompt is just an `EvalItem.prompt`. Use
`data/evalfrag/evalfrag_seed.jsonl` rows via the sweep data path mechanism
(reuse `load_items` with `paraphrase_id`-style filtering once a
`perturbation_id` loader lands in a future phase), or add a
`data/evalfrag/evalfrag_seed.jsonl` study config. Scoring is unchanged —
`is_correct(task, generation, gold)` with the copied gold.

## Status

- MEASURED: `data/paraphrase_set.jsonl` wordings (frozen human-written).
- PENDING: EvalFrag seed observed results (no model run attached yet).
- UNAVAILABLE: code / safety / hallucination perturbation families.