"""One-off analysis: per-configuration ordering and where the ranking flips.

Answers the question the held-out budget curve cannot: the curve says the
aggregate decision is predictable, but the paper's headline is rank reversal
under 5-shot prompting. This prints the per-configuration picture so the two
can be reconciled honestly.
"""
import itertools
import sys
from pathlib import Path

from apertus_eval_prep.cli import _registry_score_matrix
from apertus_eval_prep.registry import load_registry

registry = sys.argv[1] if len(sys.argv) > 1 else "results/registry_paper.jsonl"
built = _registry_score_matrix(load_registry(Path(registry)))
matrix, models, configs = built["matrix"], built["models"], built["configs"]

short = [m.split("/")[-1] for m in models]
print(f"registry : {registry}")
print(f"models   : {short}   configs: {len(configs)}   missing cells: {built['n_missing_cells']}")
print(f"excluded (<2 cells): {built['excluded_models_lt2_cells']}")
print()

header = f"{'configuration':<26}" + "".join(f"{s[:15]:>17}" for s in short) + "   winner"
print(header)
print("-" * len(header))
for ci, cfg in enumerate(configs):
    vals = [row[ci] for row in matrix]
    best = max((v for v in vals if v is not None), default=None)
    winner = short[vals.index(best)] if best is not None else "n/a"
    cells = "".join(f"{v:>17.4f}" if v is not None else f"{'--':>17}" for v in vals)
    print(f"{cfg:<26}{cells}   {winner}")

print()
print("Pairwise stability across configurations:")
for a, b in itertools.combinations(range(len(models)), 2):
    wins_a = wins_b = 0
    flip_cfgs = []
    for ci, cfg in enumerate(configs):
        va, vb = matrix[a][ci], matrix[b][ci]
        if va is None or vb is None or va == vb:
            continue
        if va > vb:
            wins_a += 1
        else:
            wins_b += 1
            flip_cfgs.append(cfg)
    total = wins_a + wins_b
    if not total:
        print(f"  {short[a]} vs {short[b]}: no decidable configuration")
        continue
    verdict = "REVERSIBLE" if 0 < min(wins_a, wins_b) else "stable ordering"
    print(f"  {short[a]} vs {short[b]}: {wins_a}/{total} vs {wins_b}/{total}  -> {verdict}")
    if flip_cfgs:
        print(f"      {short[b]} wins only on: {', '.join(flip_cfgs)}")
