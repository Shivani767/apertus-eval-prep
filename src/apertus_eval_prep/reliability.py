"""Evaluation Reliability Score (ERS) — a documented, provisional composite.

Question served: "how much can we trust the ranking this evaluation matrix
produces?" ERS aggregates FOUR already-implemented reliability components,
each in [0, 1] (higher = more reliable). Components that cannot be computed
from the provided data are reported as None and EXCLUDED from the weighted
average (weights renormalize over available components) — nothing is
imputed, and n_components tells you how much evidence backed the score.

Components
----------
1. ci_separation — fraction of model pairs whose 95% Wilson CIs do not
   overlap. REQUIRES n_per_cell (items per config cell); without a measured
   n the component is None. CIs use pooled accuracy over usable configs:
   n_total = n_per_cell * n_configs_used, k = round(acc * n_total)
   (binomial pooling approximation, documented).
2. bootstrap_tau — mean Kendall tau between the reference ranking and
   bootstrap-resampled-config rankings (ranking.bootstrap_ranking_stability),
   clamped to [0, 1]; the raw (possibly negative) value is kept in details.
3. config_stability — 1 - clamp(mean within-model std across configs /
   between-model std of model means, 0, 1). A within/between variance-ratio
   (ICC-style) reading: unstable protocols blur model differences. Undefined
   (None) when between-model std is 0 or any model has < 2 configs.
4. seed_stability — same ratio using per-model seed scores when supplied;
   None when seed_scores is not provided.

Composite: ERS = sum(w_c * c_c) / sum(w_c) over available components.
Default weights are PROVISIONAL and their sensitivity is exposed via
ers_ablation(); they encode "CI separation first, resampling stability
second, protocol/seed spread third". ERS is a descriptive summary for
exploration — NOT a validated measurement, and never a substitute for
inspecting the components.
"""

from __future__ import annotations

from statistics import mean, pstdev
from typing import Any, Sequence

from apertus_eval_prep.ranking import bootstrap_ranking_stability
from apertus_eval_prep.stats import cis_overlap, wilson_interval

DEFAULT_WEIGHTS = {
    "ci_separation": 0.4,
    "bootstrap_tau": 0.3,
    "config_stability": 0.2,
    "seed_stability": 0.1,
}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _spread_ratio(columns_per_model: Sequence[Sequence[float]]) -> float | None:
    """1 - mean within-model std / between-model std; None when undefined."""
    within = []
    for scores in columns_per_model:
        present = [s for s in scores if s is not None]
        if len(present) < 2:
            return None
        within.append(pstdev(present))
    model_means = [
        mean([s for s in scores if s is not None]) for scores in columns_per_model
    ]
    between = pstdev(model_means)
    if between == 0.0:
        return None
    return _clamp01(1.0 - mean(within) / between)


def _ci_separation(score_matrix: Sequence[Sequence[float]], n_per_cell: int) -> float | None:
    """Fraction of model pairs with non-overlapping 95% Wilson CIs."""
    n_m = len(score_matrix)
    n_c = len(score_matrix[0]) if n_m else 0
    usable = [
        c for c in range(n_c)
        if all(score_matrix[m][c] is not None for m in range(n_m))
    ]
    if n_m < 2 or not usable:
        return None
    accs, ns = [], []
    for m in range(n_m):
        vals = [score_matrix[m][c] for c in usable]
        accs.append(mean(vals))
        ns.append(n_per_cell * len(vals))
    cis = []
    for acc, n_total in zip(accs, ns):
        k = int(round(acc * n_total))
        cis.append(wilson_interval(k, n_total))
    pairs = overlap_no = 0
    for i in range(n_m):
        for j in range(i + 1, n_m):
            pairs += 1
            if cis_overlap(cis[i], cis[j]) is False:
                overlap_no += 1
    return overlap_no / pairs


def evaluation_reliability_score(
    score_matrix: Sequence[Sequence[float | None]],
    *,
    n_per_cell: int | None = None,
    seed_scores: Sequence[Sequence[float | None]] | None = None,
    n_boot: int = 300,
    seed: int = 0,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Compute ERS + component details. All inputs must already be measured.

    score_matrix: models x configs (None = unmeasured cell, config skipped).
    seed_scores:  models x seeds, same length per model, optional.
    """
    w = dict(DEFAULT_WEIGHTS if weights is None else weights)
    unknown = set(w) - set(DEFAULT_WEIGHTS)
    if unknown:
        raise ValueError(f"unknown component weights: {sorted(unknown)}")
    if not w or any(v <= 0 for v in w.values()):
        raise ValueError("weights must be positive and non-empty")

    components: dict[str, float | None] = {}

    if n_per_cell is None or n_per_cell <= 0:
        components["ci_separation"] = None
    else:
        components["ci_separation"] = _ci_separation(score_matrix, int(n_per_cell))

    bs = bootstrap_ranking_stability(score_matrix, n_boot=n_boot, seed=seed)
    raw_tau = bs["mean_tau"]
    components["bootstrap_tau"] = (
        None if raw_tau is None else _clamp01(float(raw_tau))
    )

    components["config_stability"] = _spread_ratio(score_matrix)
    components["seed_stability"] = (
        None if seed_scores is None else _spread_ratio(seed_scores)
    )

    used_w = {k: w[k] for k, v in components.items() if v is not None and k in w}
    if not used_w:
        ers = None
    else:
        ers = sum(w[k] * components[k] for k in used_w) / sum(used_w.values())
    return {
        "ers": round(ers, 4) if ers is not None else None,
        "components": components,
        "components_used": sorted(used_w),
        "weights_used": {k: round(w[k], 4) for k in sorted(used_w)},
        "n_components": len(used_w),
        "bootstrap": {k: bs[k] for k in ("mean_tau", "p_any_reversal",
                                         "n_models", "n_configs")},
        "provisional": True,
    }


def ers_ablation(
    score_matrix: Sequence[Sequence[float | None]],
    *,
    n_per_cell: int | None = None,
    seed_scores: Sequence[Sequence[float | None]] | None = None,
    n_boot: int = 300,
    seed: int = 0,
) -> dict[str, Any]:
    """ERS recomputed with each single component removed (renormalized).

    Exposes how sensitive the composite is to the provisional weights.
    """
    base = evaluation_reliability_score(
        score_matrix, n_per_cell=n_per_cell, seed_scores=seed_scores,
        n_boot=n_boot, seed=seed,
    )
    drops: dict[str, Any] = {}
    for comp in sorted(base["components_used"]):
        w = {k: v for k, v in DEFAULT_WEIGHTS.items() if k != comp}
        out = evaluation_reliability_score(
            score_matrix, n_per_cell=n_per_cell, seed_scores=seed_scores,
            n_boot=n_boot, seed=seed, weights=w,
        )
        drops[comp] = {
            "ers_without": out["ers"],
            "delta": (
                round(out["ers"] - base["ers"], 4)
                if out["ers"] is not None and base["ers"] is not None else None
            ),
        }
    return {"ers": base["ers"], "drop_one": drops}