"""Judge reliability metadata and disagreement reporting."""
from __future__ import annotations

from typing import Any, Mapping, Sequence


def judge_reliability(judgments: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Report agreement only; no external judge is required for offline runs."""
    usable = [j for j in judgments if j.get("label") is not None]
    if not usable:
        return {"n": 0, "agreement": None, "status": "INSUFFICIENT_EVIDENCE",
                "limitations": ["human or judge labels are required"]}
    groups: dict[str, list[str]] = {}
    for row in usable:
        groups.setdefault(str(row.get("example_id", "unknown")), []).append(str(row.get("label")))
    agreed = sum(len(set(labels)) == 1 for labels in groups.values())
    return {"n": len(usable), "n_examples": len(groups), "agreement": agreed / len(groups),
            "status": "MEASURED_PROJECT_LABEL_AGREEMENT" if len(groups) else "INSUFFICIENT_EVIDENCE",
            "limitations": ["agreement is not validity; adjudication and sampling bias remain"]}


__all__ = ["judge_reliability"]
