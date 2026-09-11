"""Pareto analysis: quality vs cost trade-offs across evaluated runs.

A run POINT (x = cost, y = quality) is on the efficient frontier when no
other measured point has BOTH cost <= and quality >=, with one strict.
Frontier members are a descriptive efficiency statement about the runs that
actually exist — NOT a recommendation, and never a substitute for the
uncertainty carried by each point's quality CI.

Convention: lower x (e.g. est_total_s), higher y (e.g. accuracy) is better.
Points with missing x or y are excluded from frontier computation and
reported under `excluded` — they are never placed at zero.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence


def pareto_front(
    points: Sequence[dict[str, Any]],
    *,
    x_key: str,
    y_key: str,
    label_key: str = "label",
) -> dict[str, Any]:
    """Split measured points into efficient-frontier members vs dominated.

    Returns {frontier: [...], dominated: [...], excluded: [...]}, each entry
    the original point dict plus `pareto: "frontier"|"dominated"`.
    Dominance requires both coordinates present and comparable.
    """
    usable: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for p in points:
        x, y = p.get(x_key), p.get(y_key)
        if x is None or y is None:
            excluded.append(p)
            continue
        usable.append(dict(p))

    frontier: list[dict[str, Any]] = []
    dominated: list[dict[str, Any]] = []
    for i, a in enumerate(usable):
        ax, ay = a[x_key], a[y_key]
        is_dominated = False
        for j, b in enumerate(usable):
            if i == j:
                continue
            bx, by = b[x_key], b[y_key]
            if bx <= ax and by >= ay and (bx < ax or by > ay):
                is_dominated = True
                break
        (dominated if is_dominated else frontier).append(a)
    for group, tag in ((frontier, "frontier"), (dominated, "dominated")):
        for p in group:
            p["pareto"] = tag
    return {
        "frontier": frontier,
        "dominated": dominated,
        "excluded": [dict(e, pareto="excluded") for e in excluded],
        "x_key": x_key,
        "y_key": y_key,
    }


def render_pareto_markdown(analysis: dict[str, Any]) -> str:
    """Human-readable frontier report; states the convention explicitly."""
    lines = [
        "# Pareto analysis (quality vs cost)",
        "",
        f"Convention: lower `{analysis['x_key']}` and higher `{analysis['y_key']}` is better.",
        "Frontier membership is descriptive of the evaluated runs only.",
        "",
        "| run | cost | quality | status |",
        "|---|---|---|---|",
    ]
    rows = (
        analysis["frontier"] + analysis["dominated"] + analysis["excluded"]
    )
    for p in rows:
        lines.append(
            f"| {p.get('label', '?')} | {p.get(analysis['x_key'])} "
            f"| {p.get(analysis['y_key'])} | {p['pareto']} |"
        )
    if analysis["excluded"]:
        lines.append("")
        lines.append(
            f"{len(analysis['excluded'])} point(s) excluded: missing cost or "
            "quality — not placed at zero."
        )
    return "\n".join(lines) + "\n"