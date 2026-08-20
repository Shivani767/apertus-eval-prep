from __future__ import annotations

import math
from typing import Any, Iterable, Sequence


def wilson_interval(k: int, n: int, z: float = 1.95996398454) -> tuple[float | None, float | None]:
    """Wilson score interval for a binomial proportion. Returns (lo, hi) in [0, 1]."""
    if n <= 0:
        return None, None
    k = max(0, min(int(k), n))
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    half = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n) / denom
    return max(0.0, center - half), min(1.0, center + half)


def chi2_sf_1df(x: float) -> float:
    """Survival function P(X^2_1 > x) = erfc(sqrt(x/2))."""
    if x <= 0:
        return 1.0
    return math.erfc(math.sqrt(x / 2.0))


def mcnemar(correct_a: Sequence[bool], correct_b: Sequence[bool]) -> dict[str, Any]:
    """McNemar test on paired item correctness (A = control, B = variant)."""
    if len(correct_a) != len(correct_b):
        raise ValueError("paired series must have the same length")
    b = c = both = neither = 0
    for a_ok, b_ok in zip(correct_a, correct_b):
        if a_ok and not b_ok:
            b += 1
        elif b_ok and not a_ok:
            c += 1
        elif a_ok and b_ok:
            both += 1
        else:
            neither += 1
    discordant = b + c
    n = len(correct_a)
    if discordant == 0:
        chi2 = 0.0
        p = 1.0
    else:
        # Continuity-corrected McNemar
        chi2 = (abs(b - c) - 1) ** 2 / discordant
        p = chi2_sf_1df(chi2)
    return {
        "n": n,
        "a_correct_b_wrong": b,
        "a_wrong_b_correct": c,
        "both_correct": both,
        "both_wrong": neither,
        "disagreement_rate": round(discordant / n, 4) if n else None,
        "chi2": round(chi2, 4),
        "p_value": round(p, 6),
    }


def kendall_tau_b(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Kendall's tau-b for two aligned rank (or score) vectors."""
    n = len(xs)
    if n != len(ys) or n < 2:
        return None
    conc = disc = t_x = t_y = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx = xs[i] - xs[j]
            dy = ys[i] - ys[j]
            if dx == 0 and dy == 0:
                continue
            if dx == 0:
                t_x += 1
            elif dy == 0:
                t_y += 1
            elif dx * dy > 0:
                conc += 1
            else:
                disc += 1
    denom = math.sqrt((conc + disc + t_x) * (conc + disc + t_y))
    if denom == 0:
        return None
    return (conc - disc) / denom


def rank_high_is_better(values: Sequence[float | None]) -> list[float]:
    """Competition ranks (1 = best). None sorts last. Ties get the average rank."""
    indexed = list(enumerate(values))
    indexed.sort(key=lambda iv: (iv[1] is None, -(iv[1] or 0.0)))
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg
        i = j + 1
    return ranks


def pairwise_reversals(ranks_a: Sequence[float], ranks_b: Sequence[float]) -> int:
    n = len(ranks_a)
    if n != len(ranks_b):
        raise ValueError("rank vectors must match")
    flips = 0
    for i in range(n):
        for j in range(i + 1, n):
            da = ranks_a[i] - ranks_a[j]
            db = ranks_b[i] - ranks_b[j]
            if da == 0 or db == 0:
                continue
            if da * db < 0:
                flips += 1
    return flips


def cis_overlap(ci_a: Sequence[float] | None, ci_b: Sequence[float] | None) -> bool | None:
    if not ci_a or not ci_b or len(ci_a) != 2 or len(ci_b) != 2:
        return None
    return not (ci_a[1] < ci_b[0] or ci_b[1] < ci_a[0])


def ci_aware_ties(models: Sequence[str], accuracies: Sequence[float], cis: Sequence[Sequence[float] | None]) -> list[dict[str, Any]]:
    """Pairs whose 95% CIs overlap are tied for reporting even if point ranks differ."""
    out = []
    for i in range(len(models)):
        for j in range(i + 1, len(models)):
            overlap = cis_overlap(cis[i], cis[j])
            out.append(
                {
                    "model_a": models[i],
                    "model_b": models[j],
                    "acc_a": accuracies[i],
                    "acc_b": accuracies[j],
                    "ci_overlap": overlap,
                    "point_order": (
                        models[i]
                        if accuracies[i] > accuracies[j]
                        else models[j]
                        if accuracies[j] > accuracies[i]
                        else "tie"
                    ),
                    "report_as_tie": overlap is True,
                }
            )
    return out


def item_correctness(rows: Iterable[dict], id_key: str = "id") -> dict[str, bool]:
    return {str(r[id_key]): bool(r["correct"]) for r in rows}
