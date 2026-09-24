"""End-to-end research-chain smoke run (research Phases 6-9, 20).

SYNTHETIC DATA — VALIDATION ONLY.

This script exercises the complete research workflow on simulated scores so
that every stage can be verified without GPU access:

    configuration space -> deterministic split -> held-out reliability
    -> interaction design -> adaptive budget curves -> leave-one-model-out

Outputs are written to reports/research_smoke/ with an explicit
``data: synthetic`` provenance marker. These numbers are NOT experimental
evidence for any claim about real models; they only demonstrate that the
research pipeline runs end-to-end and is deterministic.

Usage:
    python scripts/research_smoke.py [--seed 0] [--out reports/research_smoke]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from apertus_eval_prep.adaptive import budget_curves, STRATEGIES
from apertus_eval_prep.heldout import (
    heldout_reliability_experiment,
    leave_one_model_out_sweep,
    run_heldout_experiments,
)
from apertus_eval_prep.interaction import interaction_study
from apertus_eval_prep.stats import kendall_tau_b


def synthetic_study(n_models=4, n_configs=24, seed=0):
    """Simulated models x configs score matrix with planted structure.

    Model quality decreases with index; config effects are small but real;
    model 3 is unusually config-sensitive (interaction-like structure).
    """
    rng = random.Random(seed)
    models = [f"model-{chr(97 + m)}" for m in range(n_models)]
    configs = [f"cfg{i:02d}" for i in range(n_configs)]
    cfg_effect = {c: rng.uniform(-0.03, 0.03) for c in configs}
    matrix, table = [], {}
    for m, name in enumerate(models):
        base = 0.85 - 0.15 * m
        noise = 0.10 if m == n_models - 1 else 0.015  # sensitive last model
        row = []
        for c in configs:
            v = base + cfg_effect[c] + rng.uniform(-noise, noise)
            v = min(1.0, max(0.0, v))
            row.append(v)
            table.setdefault(name, {})[c] = v
        matrix.append(row)
    candidates = [{"model_id": name, "config_key": c}
                  for name in models for c in configs]
    return models, configs, matrix, table, candidates


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="reports/research_smoke")
    args = ap.parse_args()

    models, configs, matrix, table, candidates = synthetic_study(seed=args.seed)
    result: dict = {
        "data": "synthetic (validation only, NOT experimental evidence)",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "n_models": len(models),
        "n_configs": len(configs),
    }

    # 1-2. configuration space + held-out reliability across budgets
    result["heldout"] = run_heldout_experiments(
        matrix, configs, budgets=[4, 8, 12, 16], seed=args.seed, n_boot=100
    )

    # 3. interaction design (design layer only; no simulated measurement claim)
    study = {
        "study": "smoke", "experiment_id": "smoke",
        "control": {"backend": "hf", "quantization": "none", "seed": 0,
                    "temperature": 0.0, "top_p": 1.0, "prompt_id": "p0"},
        "models": models[:2],
        "factors": {"prompt_id": ["p0", "p1"],
                    "backend": ["hf", "vllm"],
                    "quantization": ["none", "int8"]},
        "sampled": {"temperature": 0.7, "top_p": 0.95},
    }
    ix = interaction_study(study, design="balanced", seed=args.seed,
                           max_cells_per_pair=3, include_control=True)
    result["interaction_design"] = {
        "n_cells": ix["n_cells"],
        "studies": {p: {"design": s["design"],
                        "selected": s["selected_size"],
                        "full": s["full_size"]}
                    for p, s in ix["studies"].items()},
    }

    # 4. adaptive budget curves (same budget for every strategy)
    strategies = ("random", "ofat", "apertus_r")
    result["budget_curves"] = budget_curves(
        table, candidates, budgets=[4, 8, 12], strategies=strategies,
        n_rep=20, seed=args.seed
    )

    # 5. leave-one-model-out generalization
    result["leave_one_model_out"] = leave_one_model_out_sweep(
        matrix, configs, budgets=[8, 16], seed=args.seed
    )

    # 6. headline summary computed FROM the artifacts above (no hand typing)
    curves = result["budget_curves"]["curves"]
    result["summary"] = {
        s: {
            "ranking_recovery@8": curves[s][8]["values"]["ranking_recovery"]["mean"],
            "ranking_recovery@12": curves[s][12]["values"]["ranking_recovery"]["mean"],
        }
        for s in strategies
    }
    full_ranking_recovery = {
        b: heldout_reliability_experiment(matrix, configs, budget=b,
                                          seed=args.seed, n_boot=0)
        for b in (4, 8, 12)
    }
    result["heldout_recovery_trend"] = {
        str(b): {"kendall_tau": full_ranking_recovery[b]["ranking_recovery"]["kendall_tau"]}
        for b in (4, 8, 12)
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "research_smoke.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=False))
    print(f"wrote {path}")
    print("summary:", json.dumps(result["summary"], indent=2))
    print("heldout recovery trend:", result["heldout_recovery_trend"])
    print("NOTE: synthetic validation only — not experimental evidence.")


if __name__ == "__main__":
    main()
