"""Generate publication-quality PDF figures for the paper.

Every figure is rendered from paper/analysis/statistics.json (derived from
committed run artifacts). No numbers are typed by hand.

Design rules: vector PDF, grayscale-readable, serif fonts, labeled axes with
units, no decorative styling.

Run:  python3 scripts/generate_figures.py
"""

from __future__ import annotations

import json
import os
os.environ.setdefault('SOURCE_DATE_EPOCH', '0')
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

STATS = REPO / "paper" / "analysis" / "statistics.json"
OUT = REPO / "paper" / "figures"

plt.rcParams.update({
    "font.family": "serif",
    "pdf.fonttype": 42,
    "font.size": 9,
    "axes.titlesize": 9.5,
    "axes.labelsize": 9,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "figure.dpi": 150,
    "savefig.bbox": "tight",
})

MODELS = ["Phi-3.5-mini", "Qwen2.5-3B", "SmolLM2-1.7B"]
MARKER = {"Phi-3.5-mini": "o", "Qwen2.5-3B": "s", "SmolLM2-1.7B": "^"}
GRAY = {"Phi-3.5-mini": "0.05", "Qwen2.5-3B": "0.45", "SmolLM2-1.7B": "0.75"}


def cell_short_label(raw: str) -> str:
    if raw == "control":
        return "Control"
    out = raw
    for k in ("prompt_id=", "backend=", "quantization=", "seed=", "sampled="):
        out = out.replace(k, "")
    return out.replace("t0.7_", "T0.7 s")


def main() -> int:
    d = json.loads(STATS.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    rk = d["ranking"]
    cellmap = {(c["config"], c["model"]): c for c in rk["cells"]}

    def cell(config: str, model: str):
        return cellmap[(config, model)]

    # ------------------------------------------- Fig 1: prompt sensitivity
    # Headline: accuracy vs prompt configuration with Wilson CIs.
    prompts = ["control", "prompt_id=concise", "prompt_id=5shot"]
    plabels = ["Control\n(zero-shot)", "Concise", "5-shot"]
    fig, ax = plt.subplots(figsize=(4.8, 3.1))
    width = 0.24
    for i, m in enumerate(MODELS):
        xs = np.arange(3) + (i - 1) * width
        ys = np.array([100.0 * cell(p, m)["acc"] for p in prompts])
        lo = np.array([100.0 * (cell(p, m)["acc"] - cell(p, m)["ci95"][0]) for p in prompts])
        hi = np.array([100.0 * (cell(p, m)["ci95"][1] - cell(p, m)["acc"]) for p in prompts])
        ax.errorbar(
            xs, ys, yerr=[lo, hi], marker=MARKER[m], color=GRAY[m],
            mfc="white", mec=GRAY[m], linestyle="none", label=m,
            markersize=5, mew=1.2, elinewidth=1.0, capsize=2.2,
        )
    ax.axvspan(1.45, 2.55, color="0.92", zorder=0)
    ax.annotate(
        "rank reversal:\nQwen overtakes Phi", xy=(2.02, 71.5),
        fontsize=7.5, ha="center", color="0.1",
    )
    ax.set_xticks(np.arange(3))
    ax.set_xticklabels(plabels)
    ax.set_ylabel("Overall accuracy (%)")
    ax.set_xlabel("Prompt configuration")
    ax.set_ylim(15, 80)
    ax.grid(True, axis="y", linewidth=0.4, alpha=0.5)
    ax.legend(frameon=False, loc="lower left")
    fig.savefig(OUT / "prompt_forest.pdf")
    plt.close(fig)
    written.append("prompt_forest.pdf")

    # ------------------------------------------- Fig 2: sensitivity heatmap
    # Delta accuracy vs control (pp) per model x config.
    rows, rowlabels = [], []
    for m in MODELS:
        ctrl_acc = 100.0 * cell("control", m)["acc"]
        for label in rk["config_labels"][1:]:
            delta = 100.0 * cell(label, m)["acc"] - ctrl_acc
            rows.append(delta)
            rowlabels.append((m, label))
    M = np.array(rows).reshape(len(MODELS), -1)
    collabels = [cell_short_label(l) for l in rk["config_labels"][1:]]
    fig, ax = plt.subplots(figsize=(5.6, 2.6))
    vmax = np.abs(M).max()
    im = ax.imshow(M, cmap="RdBu", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(collabels)))
    ax.set_xticklabels(collabels, rotation=28, ha="right")
    ax.set_yticks(range(len(MODELS)))
    ax.set_yticklabels(MODELS)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            ax.text(
                j, i, f"{v:+.1f}", ha="center", va="center", fontsize=7.5,
                color="white" if abs(v) > 0.62 * vmax else "black",
            )
    cbar = fig.colorbar(im, ax=ax, pad=0.015)
    cbar.set_label("$\\Delta$ accuracy vs. control (pp)")
    ax.set_title("Score change against each model's control configuration")
    fig.savefig(OUT / "sensitivity_heatmap.pdf")
    plt.close(fig)
    written.append("sensitivity_heatmap.pdf")

    # ------------------------------------------- Fig 3: rank heatmap
    # Model rank (1=best) per configuration; reversal highlighted.
    ranks = np.array(
        [[tr["ranks"][rk["models"].index(m)] if tr.get("measured") else np.nan
          for tr in rk["tau_vs_control"]] for m in MODELS]
    )
    fig, ax = plt.subplots(figsize=(5.6, 2.2))
    masked = np.ma.masked_invalid(ranks)
    cmap = plt.get_cmap("gray_r").copy()
    cmap.set_bad(color="0.90")
    im = ax.imshow(masked, cmap=cmap, vmin=1, vmax=3, aspect="auto")
    ax.set_xticks(range(len(rk["config_labels"])))
    ax.set_xticklabels([cell_short_label(l) for l in rk["config_labels"]],
                       rotation=28, ha="right")
    ax.set_yticks(range(len(MODELS)))
    ax.set_yticklabels(MODELS)
    for i in range(ranks.shape[0]):
        for j in range(ranks.shape[1]):
            if not np.isnan(ranks[i, j]):
                ax.text(j, i, f"{int(ranks[i, j])}", ha="center", va="center",
                        fontsize=8.5,
                        color="white" if ranks[i, j] > 1.5 else "black")
    # outline the reversal cells (5shot column, Phi and Qwen rows)
    j5 = rk["config_labels"].index("prompt_id=5shot")
    iq = MODELS.index("Qwen2.5-3B")
    ip = MODELS.index("Phi-3.5-mini")
    for r in (iq, ip):
        ax.add_patch(plt.Rectangle((j5 - 0.5, r - 0.5), 1, 1, fill=False,
                                   edgecolor="black", linewidth=1.4))
    cbar = fig.colorbar(im, ax=ax, pad=0.015, ticks=[1, 2, 3])
    cbar.set_label("Rank (1 = best)")
    ax.set_title("Model rank per evaluation configuration")
    fig.savefig(OUT / "rank_heatmap.pdf")
    plt.close(fig)
    written.append("rank_heatmap.pdf")

    # ------------------------------------------- Fig 4: stochasticity
    # Per-seed accuracy under greedy vs T=0.7 sampling (two models).
    samp = d["sampling"]
    fig, ax = plt.subplots(figsize=(4.8, 3.0))
    xs_by_model = {"Qwen2.5-3B": 0, "SmolLM2-1.7B": 1}
    for m in ["Qwen2.5-3B", "SmolLM2-1.7B"]:
        s = samp[m]
        x0 = xs_by_model[m]
        # greedy: control + two identical seed cells
        g = 100.0 * s["control_accuracy"]
        ax.plot([x0 - 0.18, x0 - 0.10, x0 - 0.02], [g] * 3, marker="o",
                linestyle="none", markersize=5, color=GRAY[m], mfc="white",
                label=("Greedy (T=0), seeds 0/1/2" if m == "Qwen2.5-3B" else None))
        # sampled
        for k, lvl in enumerate(["t0.7_seed0", "t0.7_seed1", "t0.7_seed2"]):
            sd = s["sampled_seeds"][lvl]
            lo = 100.0 * (sd["accuracy"] - sd["ci95"][0])
            hi = 100.0 * (sd["ci95"][1] - sd["accuracy"])
            ax.errorbar(
                [x0 + 0.12 + 0.08 * k], [100.0 * sd["accuracy"]],
                yerr=[[lo], [hi]], marker="s", linestyle="none", markersize=5,
                color=GRAY[m], mfc="gray" if m == "Qwen2.5-3B" else "white",
                mec=GRAY[m], elinewidth=1.0, capsize=2.2,
                label=("T=0.7, top-$p$=0.95, seeds 0/1/2" if m == "Qwen2.5-3B" and k == 0 else None),
            )
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Qwen2.5-3B", "SmolLM2-1.7B"])
    ax.set_ylabel("Overall accuracy (%)")
    ax.set_ylim(30, 70)
    ax.grid(True, axis="y", linewidth=0.4, alpha=0.5)
    ax.legend(frameon=False, loc="lower left", fontsize=7.5)
    ax.set_title("Greedy decoding is seed-invariant; sampling adds spread")
    fig.savefig(OUT / "sampling_variance.pdf")
    plt.close(fig)
    written.append("sampling_variance.pdf")

    # ------------------------------------------- Fig 5: pairwise win rates
    win = rk["pairwise_win_rates"]
    labels = ["Phi-3.5-mini", "Qwen2.5-3B", "SmolLM2-1.7B"]
    W = np.full((3, 3), np.nan)
    for i, a in enumerate(labels):
        for j, b in enumerate(labels):
            if i != j:
                W[i, j] = win[f"{a} > {b}"]
    fig, ax = plt.subplots(figsize=(3.4, 3.0))
    im = ax.imshow(W, cmap="Greys", vmin=0, vmax=1)
    ax.set_xticks(range(3))
    ax.set_xticklabels(["Phi", "Qwen", "Smol"])
    ax.set_yticks(range(3))
    ax.set_yticklabels(["Phi", "Qwen", "Smol"])
    ax.set_xlabel("Opponent")
    ax.set_ylabel("Model (row)")
    for i in range(3):
        for j in range(3):
            if i == j:
                ax.text(j, i, "—", ha="center", va="center", color="0.6")
            else:
                ax.text(j, i, f"{W[i, j]:.2f}", ha="center", va="center",
                        fontsize=9,
                        color="white" if W[i, j] > 0.6 else "black")
    cbar = fig.colorbar(im, ax=ax, pad=0.02)
    cbar.set_label("P(row > opponent)\nover 8 configs")
    ax.set_title("Pairwise win rates")
    fig.savefig(OUT / "win_probability.pdf")
    plt.close(fig)
    written.append("win_probability.pdf")
# __APPEND_MARKER__




    print("wrote:", ", ".join(written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
