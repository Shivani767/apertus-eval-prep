"""Validation fixture: synthetic registry shaped like run_t4_research rows.

NOT an experiment — CPU-only plumbing validation for analyze_research_results.py.
When analyzing this fixture ALWAYS pass --data-label synthetic so the report
can never present synthetic numbers as measurements:

    python scripts/_mk_synth_registry.py
    python scripts/analyze_research_results.py --registry /tmp/t4syn_registry.jsonl \
        --data-label synthetic --out /tmp/t4syn_analysis
"""

import json
import pathlib
import random

rng = random.Random(0)
rows = []
MODELS = ["mock/tiny-a", "mock/tiny-b", "mock/tiny-c"]
# 3 prompts x 2 backends x 2 quantization x 3 seeds = 18 (confirmation design)
for mi, model in enumerate(MODELS):
    base = [0.82, 0.74, 0.61][mi]
    for pi in range(3):
        for b in ("hf", "vllm"):
            for q in ("none", "int8"):
                for s in range(3):
                    noise = rng.uniform(-0.02, 0.02)
                    acc = min(1.0, max(0.0, base - 0.03 * pi + noise))
                    rows.append({
                        "run_id": f"{model.split('/')[-1]}_r{len(rows)}",
                        "config_hash": f"hash{len(rows):04d}",
                        "experiment_id": "t4_factorial",
                        "model_id": model,
                        "factor": "factorial",
                        "factor_level": (
                            f"backend={b}+prompt_id=p{pi}+"
                            f"quantization={q}+seed={s}"),
                        "path": None,
                        "status": "ok",
                        "git_commit": "0000000" if len(rows) % 9 else None,
                        "hardware": "mock",
                        "overall": {"accuracy": round(acc, 6)},
                    })
# one failed row (problem reporting must be explicit)
rows.append({
    "run_id": "bad_row", "config_hash": "hashbad", "experiment_id": "t4_factorial",
    "model_id": MODELS[0], "factor": "factorial",
    "factor_level": "backend=hf+prompt_id=p0+quantization=none+seed=0",
    "path": None, "status": "failed", "error": "MockRuntimeError: oom",
})
out = pathlib.Path("/tmp/t4syn_registry.jsonl")
out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
print(f"written {len(rows)} rows -> {out}")
