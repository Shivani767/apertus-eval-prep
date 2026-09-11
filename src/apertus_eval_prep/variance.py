"""Variance decomposition (Phase 6): descriptive attribution, assumptions explicit.

Methods: one-way effect sizes (eta-squared per factor, no distributional
assumptions beyond the sample), two-way interaction screen (OFAT-safe: reports
UNAVAILABLE when the design has no crossed cells instead of forcing ANOVA), and
a residual summary. ANOVA F/p values are NOT reported: with n=31 opportunistic
cells the assumptions (independence, homoscedasticity, balanced design) do not
hold, and printing F/p would invite false rigor. Every output states n, design,
missing cells, and limits.
"""

from __future__ import annotations

from statistics import mean, pvariance
from typing import Any, Sequence


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
