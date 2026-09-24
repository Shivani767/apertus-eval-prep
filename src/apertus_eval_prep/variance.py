"""Variance decomposition (Phase 6): descriptive attribution, assumptions explicit.

Methods:
- one-way effect sizes (eta-squared per factor, no distributional assumptions
  beyond the sample) — descriptive only.
- two-way interaction screen (OFAT-safe: reports UNAVAILABLE when the design
  has no crossed cells instead of forcing ANOVA).
- **factorial variance decomposition** (research Phase 3): balanced two-way
  ANOVA partitioning of the total sum of squares into main effects A, B,
  interaction AB, and residual, with bootstrap CIs and balance/completeness
  diagnostics. ANOVA is applied ONLY where the design justifies it
  (balanced, complete, independent cells); otherwise the analysis returns
  UNAVAILABLE with the reason.
"""

from __future__ import annotations

import random
from statistics import mean, pvariance
from typing import Any, Sequence

from apertus_eval_prep.stats import wilson_interval


def _vals(rows: list[dict[str, Any]], key: str = "score") -> list[float]:
    return [float(r[key]) for r in rows if r.get(key) is not None]


def eta_squared_one_way(rows: list[dict[str, Any]], factor: str) -> dict[str, Any]:
    """Descriptive eta-squared of `factor` on `score`: SS_between / SS_total.

    Rows: {factor_level..., score}. Levels with <1 scored row are listed in
    `empty_levels`, never imputed. Single-level or empty input -> None with reason.
    """
    scored = [r for r in rows if r.get("score") is not None]
    levels: dict[str, list[float]] = {}
    for r in scored:
        levels.setdefault(str(r.get(factor)), []).append(float(r["score"]))
    empty = sorted(k for k, v in levels.items() if not v)
    present = {k: v for k, v in levels.items() if v}
    if len(present) < 2:
        return {"factor": factor, "eta_squared": None, "n": len(scored),
                "n_levels": len(present), "empty_levels": empty,
                "reason": "need >=2 levels with scores"}
    grand = mean(v for vs in present.values() for v in vs)
    ss_between = sum(len(vs) * (mean(vs) - grand) ** 2 for vs in present.values())
    ss_total = pvariance([v for vs in present.values() for v in vs]) * len(scored)
    eta = (ss_between / ss_total) if ss_total > 0 else 0.0
    return {"factor": factor, "eta_squared": round(eta, 4), "n": len(scored),
            "n_levels": len(present),
            "level_means": {k: round(mean(v), 4) for k, v in present.items()},
            "empty_levels": empty}


def decompose_variance(
    rows: list[dict[str, Any]], factors: Sequence[str]
) -> dict[str, Any]:
    """Rank factors by one-way eta-squared; report residual + limits.

    Each factor is assessed marginally (OFAT designs confound factors, so shares
    need not sum to 1 — stated explicitly). Residual = 1 - max share is NOT a
    true residual; it is reported as `unattributed_by_best_single_factor`.
    """
    parts = [eta_squared_one_way(rows, f) for f in factors]
    ranked = sorted(parts, key=lambda p: (p["eta_squared"] is not None, p["eta_squared"] or 0.0),
                    reverse=True)
    best = next((p["eta_squared"] for p in ranked if p["eta_squared"] is not None), None)
    n = len([r for r in rows if r.get("score") is not None])
    return {
        "by_factor": ranked,
        "unattributed_by_best_single_factor": (round(1 - best, 4) if best is not None else None),
        "n": n,
        "assumptions": "descriptive eta-squared; OFAT cells confound factors; "
                       "shares need not sum to 1; no F/p (assumptions fail at n=%d)" % n,
    }


def interaction_screen(
    rows: list[dict[str, Any]], factor_a: str, factor_b: str
) -> dict[str, Any]:
    """OFAT-safe interaction check: needs crossed (a,b) cells with scores.

    Returns per-combo means and whether a crossed design exists. Pure OFAT data
    (one factor varies at a time) -> status UNAVAILABLE with reason, never a
    forced ANOVA on uncrossed data. Use factorial cells (sweep.expand_factorial)
    to make interactions measurable.
    """
    combos: dict[tuple[str, str], list[float]] = {}
    for r in rows:
        if r.get("score") is None:
            continue
        combos.setdefault((str(r.get(factor_a)), str(r.get(factor_b))), []).append(float(r["score"]))
    a_levels = sorted({a for a, _ in combos})
    b_levels = sorted({b for _, b in combos})
    crossed = len(a_levels) >= 2 and len(b_levels) >= 2 and len(combos) >= 4
    return {
        "factor_a": factor_a, "factor_b": factor_b,
        "combo_means": {f"{a}|{b}": round(mean(v), 4) for (a, b), v in combos.items()},
        "combo_n": {f"{a}|{b}": len(v) for (a, b), v in combos.items()},
        "crossed_design": crossed,
        "status": "MEASURED" if crossed else "UNAVAILABLE",
        "reason": None if crossed else
        "no crossed cells: OFAT varies one factor at a time; run factorial design",
    }
# ---------------------------------------------------------------------------
# Factorial (two-way) variance decomposition — research Phase 3
# ---------------------------------------------------------------------------


def _cell_means(rows: list[dict], factor_a: str, factor_b: str) -> dict[tuple[str, str], list[float]]:
    """group scored rows into (a, b) cells, preserving replication."""
    cells: dict[tuple[str, str], list[float]] = {}
    for r in rows:
        if r.get("score") is None:
            continue
        cells.setdefault((str(r[factor_a]), str(r[factor_b])), []).append(float(r["score"]))
    return cells


def factorial_diagnostics(
    rows: list[dict[str, Any]], factor_a: str, factor_b: str
) -> dict[str, Any]:
    """Balance / completeness diagnostics for the (a, b) design.

    Returns count-per-cell, whether the design is complete (all level pairs
    present) and balanced (all cells have the same replication count), plus
    which cells are missing. Only aids interpretation; it never imputes.
    """
    cells = _cell_means(rows, factor_a, factor_b)
    a_levels = sorted({k[0] for k in cells})
    b_levels = sorted({k[1] for k in cells})
    cell_n = {f"{a}|{b}": len(v) for (a, b), v in cells.items()}
    expected = {(a, b) for a in a_levels for b in b_levels}
    missing = sorted(expected - set(cells))
    counts = list(cell_n.values())
    complete = not missing
    balanced = bool(counts) and len(set(counts)) == 1
    return {
        "factor_a": factor_a,
        "factor_b": factor_b,
        "a_levels": a_levels,
        "b_levels": b_levels,
        "cell_n": cell_n,
        "complete": complete,
        "balanced": balanced,
        "n_missing_cells": len(missing),
        "missing_cells": [f"{a}|{b}" for a, b in missing],
        "min_reps": min(counts) if counts else 0,
        "max_reps": max(counts) if counts else 0,
    }


def _decomposition_sums(
    cells: dict[tuple[str, str], list[float]],
) -> dict[str, Any]:
    """Balanced two-way sums-of-squares decomposition.

    Only called when the design is complete + balanced (guarded by the caller).
    Fixed-effects model:

        Y_ijk = mu + alpha_i + beta_j + (alphabeta)_ij + e_ijk

    SS_total = SS_A + SS_B + SS_AB + SS_E  (exact partition).
    Reported effect size is omega^2 = SS_effect / SS_total (fraction of total
    variance attributable to the effect); F/p are deliberately NOT reported
    (module docstring — assumptions are design-checked, not sampled).
    """
    a_levels = sorted({k[0] for k in cells})
    b_levels = sorted({k[1] for k in cells})
    n_ab = len(cells[(a_levels[0], b_levels[0])])  # balanced by construction
    all_vals = [v for vs in cells.values() for v in vs]
    grand = mean(all_vals)
    ss_total = sum((v - grand) ** 2 for v in all_vals)
    if ss_total == 0.0:
        # Degenerate (zero-variance) data: keep the return contract complete so
        # callers can still read level/cell means; fractions resolve to None.
        return {"grand_mean": grand, "ss_total": 0.0, "ss_a": 0.0, "ss_b": 0.0,
                "ss_ab": 0.0, "ss_e": 0.0,
                "level_means_a": {a: grand for a in a_levels},
                "level_means_b": {b: grand for b in b_levels},
                "cell_means": {f"{a}|{b}": grand for a in a_levels for b in b_levels}}

    a_means = {}
    b_means = {}
    for a in a_levels:
        vals = [v for (aa, _), vs in cells.items() for v in vs if aa == a]
        a_means[a] = mean(vals)
    for b in b_levels:
        vals = [v for (_, bb), vs in cells.items() for v in vs if bb == b]
        b_means[b] = mean(vals)
    cell_means = {k: mean(v) for k, v in cells.items()}

    ss_a = n_ab * len(b_levels) * sum((a_means[a] - grand) ** 2 for a in a_levels)
    ss_b = n_ab * len(a_levels) * sum((b_means[b] - grand) ** 2 for b in b_levels)
    ss_ab = n_ab * sum(
        (cell_means[(a, b)] - a_means[a] - b_means[b] + grand) ** 2
        for a in a_levels for b in b_levels
    )
    ss_e = 0.0
    for (a, b), vs in cells.items():
        cm = cell_means[(a, b)]
        ss_e += sum((v - cm) ** 2 for v in vs)
    return {
        "grand_mean": grand, "ss_total": ss_total,
        "ss_a": ss_a, "ss_b": ss_b, "ss_ab": ss_ab, "ss_e": ss_e,
        "level_means_a": {k: round(v, 4) for k, v in a_means.items()},
        "level_means_b": {k: round(v, 4) for k, v in b_means.items()},
        "cell_means": {f"{a}|{b}": round(mean(v), 4) for (a, b), v in cells.items()},
    }
def factorial_variance_decomposition(
    rows: list[dict[str, Any]],
    factor_a: str,
    factor_b: str,
    *,
    n_boot: int = 0,
    seed: int = 0,
) -> dict[str, Any]:
    """Two-way factorial variance decomposition with diagnostics + CIs.

    Guarded policy (same philosophy as ``interaction_screen``):
    * fewer than 2 levels per axis, or < 4 crossed cells -> UNAVAILABLE.
    * incomplete or unbalanced design                     -> UNAVAILABLE
      (no forced unbalanced ANOVA; caller reruns a balanced factorial).
    * otherwise -> SS partition + omega-squared fractions; when ``n_boot > 0``
      a seeded cell-stratified bootstrap yields percentile CIs per fraction.
    """
    cells = _cell_means(rows, factor_a, factor_b)
    diag = factorial_diagnostics(rows, factor_a, factor_b)
    a_levels = diag["a_levels"]
    b_levels = diag["b_levels"]
    if len(a_levels) < 2 or len(b_levels) < 2 or len(cells) < 4:
        return {
            "factor_a": factor_a, "factor_b": factor_b, "status": "UNAVAILABLE",
            "reason": "need >= 2 levels per axis and >= 4 crossed cells",
            "diagnostics": diag,
        }
    if not diag["complete"] or not diag["balanced"]:
        return {
            "factor_a": factor_a, "factor_b": factor_b, "status": "UNAVAILABLE",
            "reason": "ANOVA requires a complete, balanced design; rerun as a "
                      "balanced factorial (see interaction.interaction_design)",
            "diagnostics": diag,
        }
    sums = _decomposition_sums(cells)

    def _fr(s):
        t = s["ss_total"]
        if t == 0.0:
            return {"factor_a": None, "factor_b": None,
                    "interaction": None, "residual": None}
        return {"factor_a": s["ss_a"] / t, "factor_b": s["ss_b"] / t,
                "interaction": s["ss_ab"] / t, "residual": s["ss_e"] / t}

    out: dict[str, Any] = {
        "factor_a": factor_a, "factor_b": factor_b, "status": "MEASURED",
        "diagnostics": diag,
        "n_observations": sum(len(v) for v in cells.values()),
        "sums_of_squares": {k: round(v, 8) for k, v in sums.items()
                            if k not in ("level_means_a", "level_means_b", "cell_means")},
        "variance_fractions": {k: (round(v, 6) if v is not None else None)
                               for k, v in _fr(sums).items()},
        "effect_sizes_omega2_pct": {k: (round((v or 0.0) * 100, 4) if v is not None else None)
                                    for k, v in _fr(sums).items()},
        "level_means_a": sums["level_means_a"],
        "level_means_b": sums["level_means_b"],
        "cell_means": sums["cell_means"],
        "assumptions": (
            "balanced complete two-way fixed-effects model, independent cells; "
            "omega^2 = SS_effect/SS_total; no F/p (assumptions design-checked)"
        ),
    }
    if n_boot > 0 and out["sums_of_squares"]["ss_total"] > 0:
        out["bootstrap_ci95"] = _bootstrap_variance_ci(
            rows, factor_a, factor_b, n_boot=n_boot, seed=seed
        )
    return out
def _bootstrap_variance_ci(
    rows: list[dict[str, Any]],
    factor_a: str,
    factor_b: str,
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """Cell-stratified bootstrap of variance fractions (percentile CI).

    Resamples WITH replacement INSIDE each (a, b) cell so balance and
    completeness are preserved in every replicate — the decomposition stays
    well-posed. Only valid when the observed design is complete + balanced.
    """
    cell_rows: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        if r.get("score") is None:
            continue
        cell_rows.setdefault((str(r[factor_a]), str(r[factor_b])), []).append(r)
    rng = random.Random(seed)
    samples: dict[str, list[float]] = {
        "factor_a": [], "factor_b": [], "interaction": [], "residual": []}
    for _ in range(n_boot):
        boot_cells: dict[tuple[str, str], list[float]] = {}
        for key, group in cell_rows.items():
            pool = [float(r["score"]) for r in group]
            boot_cells[key] = [rng.choice(pool) for _ in range(len(pool))]
        s = _decomposition_sums(boot_cells)
        t = s["ss_total"]
        if t == 0.0:
            continue
        fr = _fractions_public(s)
        for k in samples:
            v = fr.get(k)
            if v is not None:
                samples[k].append(v)
    out: dict[str, Any] = {}
    for k, vals in samples.items():
        if len(vals) < 2:
            out[k] = None
            continue
        vals.sort()
        lo = vals[max(0, int(0.025 * len(vals)))]
        hi = vals[min(len(vals) - 1, int(0.975 * len(vals)))]
        out[k] = [round(lo, 6), round(hi, 6)]
    out["n_boot"] = n_boot
    out["seed"] = seed
    return out


def _fractions_public(s: dict[str, Any]) -> dict[str, float | None]:
    t = s["ss_total"]
    if t == 0.0:
        return {"factor_a": None, "factor_b": None, "interaction": None, "residual": None}
    return {"factor_a": s["ss_a"] / t, "factor_b": s["ss_b"] / t,
            "interaction": s["ss_ab"] / t, "residual": s["ss_e"] / t}


def variance_contribution_table(
    rows: list[dict[str, Any]],
    factors: Sequence[str],
    *,
    pair: str | None = None,
    n_boot: int = 0,
    seed: int = 0,
) -> dict[str, Any]:
    """One table combining one-way contributions and (if `pair` is given) the
    two-way interaction decomposition. Never mixes designs: the one-way shares
    are marginal and need not sum to 1 (stated explicitly); the two-way entry
    is the interaction-aware partition for the pair."""
    one_way = decompose_variance(rows, factors)
    table: dict[str, Any] = {
        "one_way_by_factor": one_way["by_factor"],
        "assumptions": one_way["assumptions"],
    }
    if pair is not None and "\u00d7" in str(pair):
        a, b = str(pair).split("\u00d7")
        table["two_way"] = factorial_variance_decomposition(
            rows, a, b, n_boot=n_boot, seed=seed
        )
    return table
