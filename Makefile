.PHONY: test smoke eval-hf eval-none eval-mismatch dump compare-template sweep-dry report ci-width

PYTHON ?= python

test:
	$(PYTHON) -m pytest -q

smoke:
	$(PYTHON) -m apertus_eval_prep eval --config configs/smoke.yaml --out results/smoke.json

eval-hf:
	$(PYTHON) -m apertus_eval_prep eval --config configs/default.yaml --out results/hf_tokenizer.json

eval-none:
	$(PYTHON) -m apertus_eval_prep eval --config configs/no_template.yaml --out results/hf_none.json

eval-mismatch:
	$(PYTHON) -m apertus_eval_prep eval --config configs/mismatched.yaml --out results/hf_mismatched.json

dump:
	$(PYTHON) -m apertus_eval_prep dump-prompts --config configs/default.yaml --out results/prompts_tokenizer.txt
	$(PYTHON) -m apertus_eval_prep dump-prompts --config configs/no_template.yaml --out results/prompts_none.txt
	$(PYTHON) -m apertus_eval_prep dump-prompts --config configs/mismatched.yaml --out results/prompts_mismatched.txt

compare-template:
	$(PYTHON) -m apertus_eval_prep compare results/hf_tokenizer.json results/hf_none.json --out results/compare_template.md
	$(PYTHON) -m apertus_eval_prep compare results/hf_tokenizer.json results/hf_mismatched.json --out results/compare_mismatch.md

sweep-dry:
	$(PYTHON) -m apertus_eval_prep sweep --config configs/experiments/stability.yaml --profile t4 --dry-run --out-dir results/runs --registry results/registry.jsonl

report:
	$(PYTHON) -m apertus_eval_prep report --registry results/registry.jsonl --out reports/stability
	$(PYTHON) -m apertus_eval_prep paper-tables --registry results/registry.jsonl --out paper/_generated_tables.md

ci-width:
	$(PYTHON) -m apertus_eval_prep ci-width \
	  --run results/runs/Qwen2.5-0.5B-Instruct_control_control_4eef2dcb284b2cab.json="T4 smoke n=4" \
	  --run results/hf_tokenizer.json="Mac canary n=28" \
	  --out reports/ci_width
