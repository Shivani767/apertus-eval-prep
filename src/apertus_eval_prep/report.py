from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from apertus_eval_prep.stats import (
    ci_aware_ties,
    kendall_tau_b,
    mcnemar,
    pairwise_reversals,
    rank_high_is_better,
)


def load_run(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def overall_block(blob: dict[str, Any]) -> dict[str, Any]:
    return (blob.get("tasks") or {}).get("overall") or {}


def settings_of(blob: dict[str, Any]) -> dict[str, Any]:
    return (blob.get("manifest") or {}).get("settings") or {}


def short_model(model_id: str) -> str:
    return model_id.split("/")[-1]


def collect_runs(registry_rows: list[dict[str, Any]], repo_root: Path) -> list[dict[str, Any]]:
    out = []
    for row in registry_rows:
        if row.get("status") != "ok" or not row.get("path"):
            continue
        path = Path(row["path"])
        if not path.is_absolute():
            path = repo_root / path
        if not path.exists():
            continue
        blob = load_run(path)
        blob["_registry"] = row
        out.append(blob)
    return out


def _factor_key(blob: dict[str, Any]) -> tuple[str, str]:
    reg = blob.get("_registry") or {}
    return str(reg.get("factor") or blob.get("factor") or "control"), str(
        reg.get("factor_level") or blob.get("factor_level") or "control"
    )


def ranking_table(blobs: list[dict[str, Any]]) -> dict[str, Any]:
    """Rank models inside each (factor, level) on overall accuracy vs control."""
    by_cell: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for blob in blobs:
        model = settings_of(blob).get("model_id")
        if not model:
            continue
        by_cell[_factor_key(blob)][model] = blob

    control = by_cell.get(("control", "control"), {})
    control_models = sorted(control)
    control_acc = [overall_block(control[m]).get("accuracy") for m in control_models]
    control_ranks = rank_high_is_better(control_acc) if control_models else []
    control_rank_map = dict(zip(control_models, control_ranks))

    factor_rows = []
    for key, models_map in sorted(by_cell.items()):
        models = sorted(models_map)
        accs = [overall_block(models_map[m]).get("accuracy") for m in models]
        cis = [overall_block(models_map[m]).get("accuracy_ci95") for m in models]
        ranks = rank_high_is_better(accs)
        aligned_control = [control_rank_map.get(m) for m in models]
        tau = None
        reversals = None
        if all(r is not None for r in aligned_control) and len(models) >= 2:
            tau = kendall_tau_b(aligned_control, ranks)
            reversals = pairwise_reversals(aligned_control, ranks)
        factor_rows.append(
            {
                "factor": key[0],
                "factor_level": key[1],
                "models": [
                    {
                        "model_id": m,
                        "accuracy": accs[i],
                        "accuracy_ci95": cis[i],
                        "rank": ranks[i],
                        "control_rank": control_rank_map.get(m),
                    }
                    for i, m in enumerate(models)
                ],
                "kendall_tau_vs_control": None if tau is None else round(tau, 4),
                "rank_reversals_vs_control": reversals,
                "ci_ties": ci_aware_ties(models, [a or 0.0 for a in accs], cis),
            }
        )

    pairwise = []
    if control:
        control_model_items: dict[str, dict[str, bool]] = {}
        for model, blob in control.items():
            control_model_items[model] = {r["id"]: bool(r["correct"]) for r in blob.get("items") or []}
        for key, models_map in by_cell.items():
            if key == ("control", "control"):
                continue
            for model, blob in models_map.items():
                if model not in control_model_items:
                    continue
                a_map = control_model_items[model]
                b_map = {r["id"]: bool(r["correct"]) for r in blob.get("items") or []}
                ids = sorted(set(a_map) & set(b_map))
                if not ids:
                    continue
                test = mcnemar([a_map[i] for i in ids], [b_map[i] for i in ids])
                pairwise.append(
                    {
                        "model_id": model,
                        "factor": key[0],
                        "factor_level": key[1],
                        **test,
                    }
                )

    return {
        "control_ranking": sorted(
            [
                {
                    "model_id": m,
                    "accuracy": overall_block(control[m]).get("accuracy"),
                    "accuracy_ci95": overall_block(control[m]).get("accuracy_ci95"),
                    "rank": control_rank_map.get(m),
                }
                for m in control_models
            ],
            key=lambda r: (r.get("rank") is None, r.get("rank") or 0, r["model_id"]),
        ),
        "by_config": factor_rows,
        "mcnemar_vs_control": pairwise,
        "n_runs": len(blobs),
    }


def render_markdown_report(analysis: dict[str, Any]) -> str:
    lines = [
        "# Ranking stability report",
        "",
        "Generated from `results/registry.jsonl`. Numbers are generative exact-match,",
        "not lm-eval loglikelihood. Wilson 95% CIs. Rank flips whose CIs overlap are ties.",
        "",
        f"Runs loaded: {analysis.get('n_runs', 0)}",
        "",
        "## Control ranking",
        "",
        "| rank | model | accuracy | 95% CI |",
        "|---|---|---|---|",
    ]
    for row in analysis.get("control_ranking") or []:
        ci = row.get("accuracy_ci95")
        ci_s = f"[{ci[0]}, {ci[1]}]" if ci else "—"
        lines.append(f"| {row.get('rank')} | `{row.get('model_id')}` | {row.get('accuracy')} | {ci_s} |")
    lines += ["", "## Kendall tau vs control", "", "| factor | level | tau-b | rank reversals | n models |", "|---|---|---|---|---|"]
    for row in analysis.get("by_config") or []:
        n = len(row.get("models") or [])
        lines.append(
            f"| {row['factor']} | {row['factor_level']} | {row.get('kendall_tau_vs_control')} | "
            f"{row.get('rank_reversals_vs_control')} | {n} |"
        )
    lines += ["", "## McNemar vs control (same items)", "", "| model | factor | level | disagree | p |", "|---|---|---|---|---|"]
    for row in analysis.get("mcnemar_vs_control") or []:
        lines.append(
            f"| `{row['model_id']}` | {row['factor']} | {row['factor_level']} | "
            f"{row.get('disagreement_rate')} | {row.get('p_value')} |"
        )
    lines += ["", "## CI-overlap ties (control)", ""]
    control_cfg = next((r for r in analysis.get("by_config") or [] if r["factor"] == "control"), None)
    if control_cfg:
        lines += ["| model A | model B | point order | CI overlap (report as tie) |", "|---|---|---|---|"]
        for pair in control_cfg.get("ci_ties") or []:
            lines.append(
                f"| `{pair['model_a']}` | `{pair['model_b']}` | {pair['point_order']} | {pair['report_as_tie']} |"
            )
    lines.append("")
    return "\n".join(lines)


def paper_tables(analysis: dict[str, Any]) -> str:
    lines = [
        "<!-- generated by: python -m apertus_eval_prep paper-tables -->",
        "",
        "### Control ranking (overall generative accuracy)",
        "",
        "| Rank | Model | Acc. | 95% Wilson CI |",
        "|---:|---|---:|---|",
    ]
    for row in analysis.get("control_ranking") or []:
        ci = row.get("accuracy_ci95")
        ci_s = f"[{ci[0]:.3f}, {ci[1]:.3f}]" if ci else "—"
        acc = row.get("accuracy")
        acc_s = "—" if acc is None else f"{acc:.3f}"
        lines.append(f"| {row.get('rank')} | `{short_model(row.get('model_id') or '')}` | {acc_s} | {ci_s} |")
    if not analysis.get("control_ranking"):
        lines.append("| — | *no GPU sweep yet* | — | — |")
    lines += [
        "",
        "### Ranking agreement with control (Kendall $\\tau_b$)",
        "",
        "| Factor | Level | $\\tau_b$ | Pairwise reversals |",
        "|---|---|---:|---:|",
    ]
    for row in analysis.get("by_config") or []:
        if row["factor"] == "control":
            continue
        lines.append(
            f"| {row['factor']} | {row['factor_level']} | {row.get('kendall_tau_vs_control')} | "
            f"{row.get('rank_reversals_vs_control')} |"
        )
    if len([r for r in analysis.get("by_config") or [] if r["factor"] != "control"]) == 0:
        lines.append("| — | *fill after Colab sweep* | — | — |")
    lines.append("")
    return "\n".join(lines)


def write_plots(analysis: dict[str, Any], out_dir: Path) -> list[str]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    # Forest: control accuracies with CI
    control = analysis.get("control_ranking") or []
    if control:
        fig, ax = plt.subplots(figsize=(8, 3 + 0.4 * len(control)))
        ys = list(range(len(control)))
        accs = [r.get("accuracy") or 0 for r in control]
        los, his = [], []
        for r in control:
            ci = r.get("accuracy_ci95") or [r.get("accuracy") or 0, r.get("accuracy") or 0]
            los.append(accs[len(los)] - ci[0])
            his.append(ci[1] - accs[len(his)])
        labels = [short_model(r.get("model_id") or "") for r in control]
        ax.errorbar(accs, ys, xerr=[los, his], fmt="o", capsize=4)
        ax.set_yticks(ys)
        ax.set_yticklabels(labels)
        ax.set_xlabel("overall accuracy (Wilson 95% CI)")
        ax.set_xlim(0, 1)
        ax.invert_yaxis()
        ax.set_title("Control ranking")
        fig.tight_layout()
        path = out_dir / "forest_control.png"
        fig.savefig(path, dpi=140)
        plt.close(fig)
        written.append(str(path))

    # Kendall bars
    rows = [r for r in analysis.get("by_config") or [] if r["factor"] != "control"]
    if rows:
        fig, ax = plt.subplots(figsize=(9, 3 + 0.35 * len(rows)))
        labels = [f"{r['factor']}={r['factor_level']}" for r in rows]
        taus = [r.get("kendall_tau_vs_control") or 0 for r in rows]
        ax.barh(labels, taus)
        ax.set_xlabel("Kendall tau-b vs control ranking")
        ax.set_xlim(-1.05, 1.05)
        ax.axvline(0, color="gray", linewidth=0.8)
        fig.tight_layout()
        path = out_dir / "kendall_tau.png"
        fig.savefig(path, dpi=140)
        plt.close(fig)
        written.append(str(path))

    # Rank heatmap
    configs = analysis.get("by_config") or []
    if configs:
        model_ids = []
        for r in configs:
            for m in r.get("models") or []:
                if m["model_id"] not in model_ids:
                    model_ids.append(m["model_id"])
        if model_ids:
            mat = []
            col_labels = []
            for r in configs:
                rank_map = {m["model_id"]: m.get("rank") for m in r.get("models") or []}
                mat.append([rank_map.get(m) if rank_map.get(m) is not None else float("nan") for m in model_ids])
                col_labels.append(f"{r['factor']}={r['factor_level']}")
            arr = list(map(list, zip(*mat)))
            fig, ax = plt.subplots(figsize=(max(6, 0.55 * len(col_labels) + 3), 2 + 0.4 * len(model_ids)))
            im = ax.imshow(arr, aspect="auto")
            ax.set_yticks(range(len(model_ids)))
            ax.set_yticklabels([short_model(m) for m in model_ids])
            ax.set_xticks(range(len(col_labels)))
            ax.set_xticklabels(col_labels, rotation=75, ha="right", fontsize=8)
            fig.colorbar(im, ax=ax, label="rank (1=best)")
            ax.set_title("Model rank by evaluation config")
            fig.tight_layout()
            path = out_dir / "rank_heatmap.png"
            fig.savefig(path, dpi=140)
            plt.close(fig)
            written.append(str(path))

    return written


def write_html(md_path: Path, plot_paths: list[str], html_path: Path) -> None:
    imgs = "".join(f'<p><img src="{Path(p).name}" alt="{Path(p).stem}" style="max-width:100%"></p>\n' for p in plot_paths)
    body = f"<pre>{md_path.read_text(encoding='utf-8')}</pre>\n{imgs}"
    html_path.write_text(
        "<!doctype html><meta charset='utf-8'><title>Ranking stability</title>"
        f"<body style='font-family:sans-serif;max-width:960px;margin:2rem auto'>{body}</body>\n",
        encoding="utf-8",
    )
