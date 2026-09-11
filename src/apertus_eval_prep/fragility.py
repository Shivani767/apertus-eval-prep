"""Fragility components + provisional EFI (Phase 4).

Fragility = how easily conclusions change under reasonable protocol changes.
Components first (score/range/std, rank tau/reversals, per-factor sensitivity,
CI-tie fragility, sampling spread). Composite EFI is PROVISIONAL: documented
formula, normalization, weights, limits + ablation. Components ship first.
"""

from __future__ import annotations

from statistics import mean
from typing import Any, Sequence

from apertus_eval_prep import stability
from apertus_eval_prep.ranking import rank_distributions
from apertus_eval_prep.stats import (
    ci_aware_ties,
    kendall_tau_b,
    pairwise_reversals,
    rank_high_is_better,
)


def score_sensitivity(scores: Sequence[float]) -> dict[str, Any]:
    """Range + std + CV of scores across configs (descriptive, measured only)."""
    vals = [float(s) for s in scores if s is not None]
    return {
        "n": len(vals),
        "mean": mean(vals) if vals else None,
        "range": stability.score_range(vals),
        "std": stability.score_std(vals),
        "cv": stability.coef_of_variation(vals),
    }


def rank_sensitivity(
    control_scores: Sequence[float], variant_scores: Sequence[float]
) -> dict[str, Any]:
    """Rank agreement between two aligned model orderings (None-safe)."""
    if len(control_scores) != len(variant_scores) or len(control_scores) < 2:
        return {"kendall_tau": None, "reversals": None, "n_models": len(control_scores)}
    rc = rank_high_is_better(list(control_scores))
    rv = rank_high_is_better(list(variant_scores))
    return {
        "kendall_tau": kendall_tau_b(rc, rv),
        "reversals": pairwise_reversals(rc, rv),
        "n_models": len(control_scores),
    }


def per_factor_sensitivity(
    by_factor: dict[str, dict[str, list[float]]],
) -> dict[str, dict[str, Any]]:
    """Max |mean delta| per factor via stability.factor_sensitivity."""
    return {f: stability.factor_sensitivity(levels) for f, levels in by_factor.items()}


def tie_fragility(
    models: Sequence[str], accuracies: Sequence[float], cis: Sequence[Any]
) -> dict[str, Any]:
    """How many model pairs are CI-overlap ties (point ranking overstates them)."""
    pairs = ci_aware_ties(list(models), list(accuracies), list(cis))
    tied = sum(1 for p in pairs if p.get("report_as_tie"))
    return {
        "n_pairs": len(pairs),
        "n_ties": tied,
        "tie_fraction": (tied / len(pairs)) if pairs else None,
    }


def sampling_spread(seed_scores: Sequence[float]) -> dict[str, Any]:
    """Spread across repeated sampling runs (same config, different seeds)."""
    return score_sensitivity(seed_scores)

DEFAULT_EFI_WEIGHTS = {
    "score_range": 0.30,
    "rank_instability": 0.35,
    "tie_fraction": 0.15,
    "sampling_cv": 0.20,
}


def evaluation_fragility_index(
    *,
    score_range: float | None,
    kendall_tau: float | None,
    tie_fraction: float | None,
    sampling_cv: float | None,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """PROVISIONAL composite EFI in [0, 1] (higher = more fragile).

    w_range*min(range,1) + w_rank*(1-tau)/2 + w_tie*tie + w_samp*min(cv,1).
    tau None (<2 shared models) -> maximally-uncertain 0.5 rank term, flagged.
    Missing range/tie/cv contribute 0 weight (renormalized), listed in missing.
    Weights renormalized; empty/zero/negative weights raise. See efi_ablation.
    """
    w = dict(DEFAULT_EFI_WEIGHTS if weights is None else weights)
    if not w or any(v < 0 for v in w.values()) or sum(w.values()) <= 0:
        raise ValueError("weights must be non-empty, non-negative, and sum > 0")
    total = sum(w.values())
    w = {k: v / total for k, v in w.items()}
    terms: dict[str, float | None] = {}
    terms["score_range"] = min(max(float(score_range), 0.0), 1.0) \
        if score_range is not None else None
    if kendall_tau is None:
        terms["rank_instability"] = 0.5
    else:
        terms["rank_instability"] = (1.0 - max(-1.0, min(1.0, float(kendall_tau)))) / 2.0
    terms["tie_fraction"] = min(max(float(tie_fraction), 0.0), 1.0) \
        if tie_fraction is not None else None
    terms["sampling_cv"] = min(max(float(sampling_cv), 0.0), 1.0) \
        if sampling_cv is not None else None
    missing = [k for k, v in terms.items() if v is None and k != "rank_instability"]
    usable = {k: v for k, v in terms.items() if v is not None and k in w}
    w_sum = sum(w[k] for k in usable)
    efi = sum(usable[k] * w[k] for k in usable) / w_sum if w_sum > 0 else None
    if w_sum == 0:
        missing = sorted(set(terms) - set(usable))
    return {"efi": efi, "terms": terms, "weights": w, "missing": missing,
            "tau_undefined": kendall_tau is None, "provisional": True}


def efi_ablation(
    *,
    score_range: float | None,
    kendall_tau: float | None,
    tie_fraction: float | None,
    sampling_cv: float | None,
) -> dict[str, dict[str, Any]]:
    """Leave-one-term-out EFI: drop each term, renormalize, delta vs full."""
    full = evaluation_fragility_index(
        score_range=score_range, kendall_tau=kendall_tau,
        tie_fraction=tie_fraction, sampling_cv=sampling_cv)
    out: dict[str, dict[str, Any]] = {"full": full}
    for drop in DEFAULT_EFI_WEIGHTS:
        w = {k: v for k, v in DEFAULT_EFI_WEIGHTS.items() if k != drop}
        rep = evaluation_fragility_index(
            score_range=score_range, kendall_tau=kendall_tau,
            tie_fraction=tie_fraction, sampling_cv=sampling_cv, weights=w)
        delta = None
        if full["efi"] is not None and rep["efi"] is not None:
            delta = rep["efi"] - full["efi"]
        out[f"drop_{drop}"] = {"efi": rep["efi"], "delta_vs_full": delta}
    return out


def model_rank_summary(
    models: Sequence[str], score_matrix: Sequence[Sequence[float]]
) -> list[dict[str, Any]]:
    """Per-model rank summary joining rank_distributions with model ids."""
    return [{"model_id": m, **d} for m, d in zip(models, rank_distributions(score_matrix))]
