# Paper-matrix figures

Generated from `results/registry_paper.jsonl` only. No hand-typed numbers.

```bash
make figures
# or: python -m apertus_eval_prep report --registry results/registry_paper.jsonl --out reports/stability_paper
```

| file | what it shows |
|---|---|
| `forest_control.png` | Control accuracies with Wilson 95% CIs |
| `prompt_ofat.png` | `prompt_id` OFAT bars + CIs (scores move; two-model τ_b = 1.0) |
| `kendall_tau.png` | Kendall τ_b vs control (undefined cells omitted) |
| `rank_heatmap.png` | Model rank by config cell |
| `stability.md` | Markdown tables from the same analysis |
