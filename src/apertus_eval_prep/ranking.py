"""Ranking robustness layer (Phase 3). Reuses stats.rank_high_is_better.

All inputs are already-measured score vectors — no runs are invented.
Spearman: Pearson correlation of competition ranks (average-tie), None when a
rank vector has zero variance. Win-rates / rank distributions / P(#1) are
empirical frequencies over the given configs. Bootstrap rank stability resamples
configs (not items) with a fixed seed for reproducibility.
"""

from __future__ import annotations

import math
import random
import statistics
from typing import Any, Mapping, Sequence

from apertus_eval_prep.stats import kendall_tau_b, rank_high_is_better


def spearman_rank_correlation(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Spearman rho via Pearson correlation of competition ranks. None if degenerate."""
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    rx = rank_high_is_better(list(xs))
    ry = rank_high_is_better(list(ys))
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return (num / den) if den else None


def pairwise_win_rates(score_matrix: Sequence[Sequence[float]]) -> list[list[float | None]]:
    """Fraction of configs where row model strictly beats column model.

    score_matrix[m][c] = accuracy of model m under config c. Missing (None)
    configs are skipped pairwise; diagonal is None. Ties are not wins.
    """
    n_m = len(score_matrix)
    out: list[list[float | None]] = [[None] * n_m for _ in range(n_m)]
    for i in range(n_m):
        for j in range(n_m):
            if i == j:
                continue
            wins = tot = 0
            for a, b in zip(score_matrix[i], score_matrix[j]):
                if a is None or b is None:
                    continue
                tot += 1
                if a > b:
                    wins += 1
            out[i][j] = (wins / tot) if tot else None
    return out


def rank_distributions(score_matrix: Sequence[Sequence[float]]) -> list[dict[str, float | int]]:
    """Per-model rank histogram over configs: mean/var rank, P(#1), n configs.

    Ranks use competition ranking (1 = best); configs with any missing score for
    the model set are skipped and counted in `n_skipped`.
    """
    n_m = len(score_matrix)
    n_c = len(score_matrix[0]) if n_m else 0
    dists = []
    skipped = 0
    cols: list[list[float]] = []
    for c in range(n_c):
        col = [score_matrix[m][c] for m in range(n_m)]
        if any(v is None for v in col):
            skipped += 1
            continue
        cols.append(rank_high_is_better(col))
    for m in range(n_m):
        ranks = [cols[c][m] for c in range(len(cols))]
        dists.append(
            {
                "mean_rank": statistics.mean(ranks) if ranks else None,
                "rank_variance": statistics.pvariance(ranks) if len(ranks) > 1 else 0.0,
                "p_rank_1": sum(1 for r in ranks if r == 1.0) / len(ranks) if ranks else None,
                "rank_min": min(ranks) if ranks else None,
                "rank_max": max(ranks) if ranks else None,
                "n_configs": len(ranks),
                "n_skipped": skipped,
            }
        )
    return dists


def bootstrap_ranking_stability(
    score_matrix: Sequence[Sequence[float]],
    *,
    n_boot: int = 1000,
    seed: int = 0,
) -> dict[str, float | int | None]:
    """Resample configs with replacement; report mean Kendall-tau vs full ranking.

    Reference ranking = competition ranks on per-model mean accuracy.
    Each bootstrap replicate ranks models on resampled-config means and compares
    with Kendall tau-b. Returns mean tau, fraction of replicates with a pairwise
    reversal vs reference, n models/configs. Deterministic given seed.
    """
    from apertus_eval_prep.stats import pairwise_reversals

    n_m = len(score_matrix)
    full = [r for r in zip(*score_matrix)]
    usable = [c for c in full if all(v is not None for v in c)]
    if n_m < 2 or not usable:
        return {"mean_tau": None, "p_any_reversal": None,
                "n_models": n_m, "n_configs": len(usable)}
    # Column INDICES that are fully measured — positions, not column tuples.
    usable_idx = [
        c for c in range(len(score_matrix[0]))
        if all(score_matrix[m][c] is not None for m in range(n_m))
    ]
    ref_acc = [statistics.mean(score_matrix[m][c] for c in usable_idx) for m in range(n_m)]
    ref_ranks = rank_high_is_better(ref_acc)
    rng = random.Random(seed)
    taus: list[float] = []
    reversals = 0
    for _ in range(n_boot):
        sample = [rng.choice(usable) for _ in usable]
        acc = [statistics.mean(col[m] for col in sample) for m in range(n_m)]
        ranks = rank_high_is_better(acc)
        tau = kendall_tau_b(ref_ranks, ranks)
        taus.append(1.0 if tau is None else tau)
        if pairwise_reversals(ref_ranks, ranks) > 0:
            reversals += 1
    return {"mean_tau": statistics.mean(taus), "p_any_reversal": reversals / n_boot,
            "n_models": n_m, "n_configs": len(usable)}


# ---------------------------------------------------------------------------
# Ranking stability (P0): how often does a perturbation change the ordering?
#
# These are deliberately kept as separate, individually named metrics. Kendall
# tau, top-1 agreement and pairwise inversion rate answer different questions
# and disagree in exactly the cases that matter -- a small pair flip deep in
# the ranking barely moves tau but can matter entirely to a top-2 selection --
# so collapsing them into one "stability score" would hide the disagreement
# that is the actual finding.
# ---------------------------------------------------------------------------

RANKING_STABILITY_DISCLAIMER = (
    "Ranking-stability metrics describe ordering agreement across evaluated "
    "configurations. They are engineering diagnostics and are not a model "
    "quality judgement, a statistical test, or production approval."
)


def _order(models: Sequence[str], scores: Sequence[float | None]) -> list[str] | None:
    """Best-first model order, or None when any score is unmeasured.

    Ties are broken by model name so the order is deterministic; a tied pair
    therefore contributes a stable order rather than an arbitrary one.
    """
    if len(models) != len(scores) or any(value is None for value in scores):
        return None
    return [
        str(model)
        for model, _ in sorted(
            zip(models, scores), key=lambda pair: (-float(pair[1]), str(pair[0]))
        )
    ]


def rank_reversal_rate(
    models: Sequence[str],
    baseline_scores: Sequence[float | None],
    perturbed_rows: Sequence[Sequence[float | None]],
) -> dict[str, Any]:
    """Fraction of valid perturbations whose best-first ordering differs.

    ``rank_reversal_rate = changed_orderings / valid_perturbations``

    A perturbation is *valid* when it scored the same model set as the
    baseline. One missing a model is recorded as incomparable and excluded
    from the denominator: a model that was never measured is not evidence that
    the ranking held.
    """
    from apertus_eval_prep.stats import pairwise_reversals

    baseline_order = _order(models, baseline_scores)
    baseline_ranks = (
        rank_high_is_better([float(v) for v in baseline_scores]) if baseline_order else None
    )
    changed: list[dict[str, Any]] = []
    incomparable: list[dict[str, Any]] = []
    tau_values: list[float] = []
    inversion_counts: list[int] = []
    same_top_one = 0

    for index, row in enumerate(perturbed_rows):
        order = _order(models, row)
        if order is None:
            incomparable.append({
                "perturbation": index,
                "reason": "a model score was not measured; ordering is undefined",
            })
            continue
        if baseline_order is None:
            changed.append({"perturbation": index, "reason": "baseline ordering undefined"})
            continue
        ranks = rank_high_is_better([float(v) for v in row])
        inversions = pairwise_reversals(baseline_ranks, ranks)
        inversion_counts.append(inversions)
        tau = kendall_tau_b(baseline_ranks, ranks)
        if tau is not None:
            tau_values.append(tau)
        if order[:1] == baseline_order[:1]:
            same_top_one += 1
        if order != baseline_order:
            changed.append({
                "perturbation": index,
                "order": order,
                "pairwise_inversions": inversions,
            })

    valid = len(perturbed_rows) - len(incomparable)
    total_pairs = len(models) * (len(models) - 1) // 2
    return {
        "metric": "rank_reversal_rate",
        "baseline_order": baseline_order,
        "n_perturbations": len(perturbed_rows),
        "valid_perturbations": valid,
        "changed_orderings": len(changed),
        "rank_reversal_rate": (len(changed) / valid) if valid else None,
        "top_1_stability": (same_top_one / valid) if valid else None,
        "mean_pairwise_inversion_rate": (
            sum(inversion_counts) / (valid * total_pairs) if valid and total_pairs else None
        ),
        "mean_kendall_tau": statistics.mean(tau_values) if tau_values else None,
        "definition": "changed best-first orderings / valid perturbations",
        "changed": changed,
        "incomparable": incomparable,
    }


def top_k_set_stability(
    models: Sequence[str],
    baseline_scores: Sequence[float | None],
    perturbed_rows: Sequence[Sequence[float | None]],
    *,
    k: int = 1,
) -> dict[str, Any]:
    """Fraction of valid perturbations preserving the same top-k *set*.

    Set-based rather than order-based on purpose: swapping ranks 1 and 2 is
    still the same selection when a deployment only ships the top two. Both
    readings are reported so the reader can apply whichever matches the real
    decision rather than having one imposed.
    """
    if k < 1:
        raise ValueError("k must be >= 1")
    baseline_order = _order(models, baseline_scores)
    if baseline_order is None:
        return {
            "metric": "top_k_set_stability",
            "k": k,
            "top_k_stability": None,
            "valid_perturbations": 0,
            "reason": "baseline ordering is undefined; no unmeasured model can be ranked",
        }
    baseline_top = set(baseline_order[:k])
    valid = 0
    set_matches = 0
    order_matches = 0
    for row in perturbed_rows:
        order = _order(models, row)
        if order is None:
            continue
        valid += 1
        if set(order[:k]) == baseline_top:
            set_matches += 1
            if order[:k] == baseline_order[:k]:
                order_matches += 1
    return {
        "metric": "top_k_set_stability",
        "k": k,
        "baseline_top_k": sorted(baseline_top),
        "valid_perturbations": valid,
        "top_k_stability": (set_matches / valid) if valid else None,
        "top_k_exact_order_stability": (order_matches / valid) if valid else None,
        "definition": "unchanged top-k set / valid perturbations",
    }


def ranking_stability_report(
    models: Sequence[str],
    baseline_scores: Sequence[float | None],
    perturbed_rows: Sequence[Sequence[float | None]],
    *,
    k: int = 1,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble every ranking-stability metric side by side, unc collapsed.

    The report intentionally exposes several agreement statistics that will
    disagree with each other. A single weighted composite would have to pick a
    weighting that encodes a decision the platform cannot justify, and would
    hide the cases where a deep pair flip and a top-1 flip look identical.
    """
    from apertus_eval_prep.core.evidence import normalize_evidence

    reversal = rank_reversal_rate(models, baseline_scores, perturbed_rows)
    top_k = top_k_set_stability(models, baseline_scores, perturbed_rows, k=k)
    return {
        "metric": "ranking_stability",
        "schema_version": "1.0",
        "models": [str(model) for model in models],
        "baseline_scores": list(baseline_scores),
        "k": k,
        "rank_reversal_rate": reversal["rank_reversal_rate"],
        "top_1_stability": reversal["top_1_stability"],
        "top_k_stability": top_k["top_k_stability"],
        "top_k_exact_order_stability": top_k["top_k_exact_order_stability"],
        "mean_kendall_tau": reversal["mean_kendall_tau"],
        "mean_pairwise_inversion_rate": reversal["mean_pairwise_inversion_rate"],
        "valid_perturbations": reversal["valid_perturbations"],
        "incomparable_perturbations": len(reversal["incomparable"]),
        "detail": {"reversal": reversal, "top_k": top_k},
        "composite_score": None,
        "composite_rationale": (
            "No composite stability score is produced. Kendall tau, top-1 "
            "agreement and pairwise inversion rate disagree in exactly the "
            "cases worth reading, so each is reported on its own."
        ),
        "disclaimer": RANKING_STABILITY_DISCLAIMER,
        "evidence": normalize_evidence(evidence),
    }



