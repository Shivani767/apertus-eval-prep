# Dataset & model catalog

content_sha256 / n / languages: MEASURED from frozen files;
model coverage: DERIVED from the experiment registry;
revisions: UNAVAILABLE unless a run recorded one.

| dataset_id | file | sha256[:12] | n | languages | status |
|---|---|---|---|---|---|
| allenai/ai2_arc:test | arc_easy.jsonl | 39fe29aa22fc | 200 | en | MEASURED |
| openai/gsm8k:test | gsm8k.jsonl | 48994e78b691 | 200 | en | MEASURED |
| Rowan/hellaswag:validation | hellaswag.jsonl | dc0c01dd2eed | 200 | en | MEASURED |
| juletxara/mgsm:test | mgsm.jsonl | 0247e7c1303a | 200 | de, en, fr | MEASURED |
| apertus-frozen-eval-set | eval_set.jsonl | a3204f98ca69 | 800 | de, en, fr | MEASURED |

| model | revision | backends | quants | cells |
|---|---|---|---|---|
| HuggingFaceTB/SmolLM2-1.7B-Instruct | none recorded | hf, vllm | int4, int8, none | 11 |
| Qwen/Qwen2.5-3B-Instruct | none recorded | hf, vllm | int4, int8, none | 11 |
| Qwen/Qwen2.5-7B-Instruct | none recorded | hf | int4 | 1 |
| microsoft/Phi-3.5-mini-instruct | none recorded | hf, vllm | int4, int8, none | 8 |
