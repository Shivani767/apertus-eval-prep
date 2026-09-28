"""Multilingual evaluation: a declared, small, evidence-labelled track.

Scope is deliberately three conditions -- English, Hindi, and Hindi-English
code-switched ("Hinglish") -- because a multilingual *finding* requires measured
items in each condition, and adding languages would produce volume, not evidence.

The central question is not "which language is best". It is: **does evaluation
sensitivity change across language and code-switching conditions?** That is the
same question the rest of the platform asks about configuration factors, applied
to language.

One design decision differs from metamorphic testing and is worth stating. A
paraphrase transformation is *designed inert*, so failing to preserve the answer
violates a declared relation. A code-switched input is *expected* to change
performance -- that is the thing being studied. So ``hinglish`` declares
``expected_relation: "not_invariant"`` and its movement is reported as a
measurement, never as a failure. Scoring a genuine code-switching effect as a
"violation" would report the finding backwards.
"""

from __future__ import annotations

import statistics
from typing import Any, Mapping, Sequence

from apertus_eval_prep.core.evidence import normalize_evidence

MULTILINGUAL_SCHEMA_VERSION = "1.0"

MULTILINGUAL_DISCLAIMER = (
    "Multilingual results describe measured scores in the declared language "
    "conditions on the evaluated items. They are not a claim about language "
    "competence in general, and no language ranking is asserted without a "
    "declared comparison and an uncertainty estimate. These are engineering "
    "diagnostics, not production approval."
)

#: The declared conditions. Adding a language requires declaring items for it.
LANGUAGE_CONDITIONS: tuple[str, ...] = ("en", "hi", "hinglish")

#: A code-switched input is expected to move the score. Declared, not assumed.
EXPECTED_RELATION_BY_CONDITION: dict[str, str] = {
    "en": "invariant",
    "hi": "invariant",
    "hinglish": "not_invariant",
}

#: The code-switched condition.
CODE_SWITCHED = "hinglish"


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _pair_deltas(
    validated: Sequence[Mapping[str, Any]], reference: str
) -> list[dict[str, Any]]:
    """Paired per-item deltas against the reference condition.

    Only items present in BOTH conditions are compared, so a condition with more
    items cannot look better on coverage alone.
    """
    reference_scores = {
        str(r.get("item_id")): float(r["score"])
        for r in validated if str(r["condition"]) == reference
    }
    paired: list[dict[str, Any]] = []
    for row in validated:
        condition = str(row["condition"])
        if condition == reference:
            continue
        item_id = str(row.get("item_id"))
        if item_id not in reference_scores:
            continue
        paired.append({
            "item_id": item_id,
            "condition": condition,
            "reference": reference,
            "reference_score": reference_scores[item_id],
            "condition_score": float(row["score"]),
            "delta": round(float(row["score"]) - reference_scores[item_id], 6),
            "expected_relation": EXPECTED_RELATION_BY_CONDITION.get(condition),
        })
    return sorted(paired, key=lambda p: (p["condition"], p["item_id"]))


def language_sensitivity_report(
    rows: Sequence[Mapping[str, Any]],
    *,
    reference_condition: str = "en",
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare conditions against a declared reference; report what is missing.

    ``rows`` are scored items carrying ``item_id``, ``condition`` and a numeric
    ``score``, plus ``model`` when a model column is present.
    """
    if reference_condition not in LANGUAGE_CONDITIONS:
        raise ValueError(
            f"reference_condition {reference_condition!r} is not a declared "
            f"condition; expected one of {LANGUAGE_CONDITIONS}"
        )
    validated = [
        row for row in rows
        if str(row.get("condition") or "") in LANGUAGE_CONDITIONS
        and _number(row.get("score")) is not None
    ]
    unknown = sorted({
        str(row.get("condition")) for row in rows
        if str(row.get("condition") or "") not in LANGUAGE_CONDITIONS
    })
    by_condition: dict[str, list[float]] = {}
    for row in validated:
        by_condition.setdefault(str(row["condition"]), []).append(float(row["score"]))

    paired = _pair_deltas(validated, reference_condition)
    comparison: list[dict[str, Any]] = []
    for condition in sorted(set(by_condition) - {reference_condition}):
        deltas = [p["delta"] for p in paired if p["condition"] == condition]
        if not deltas:
            comparison.append({
                "condition": condition,
                "n_paired_items": 0,
                "mean_delta_vs_reference": None,
                "sd_of_deltas": None,
                "expected_relation": EXPECTED_RELATION_BY_CONDITION.get(condition),
                "status": "UNAVAILABLE",
                "reason": "no item_id is shared with the reference condition, so no "
                          "paired comparison is possible; this is not a zero delta",
            })
            continue
        comparison.append({
            "condition": condition,
            "n_paired_items": len(deltas),
            "mean_delta_vs_reference": round(statistics.mean(deltas), 6),
            "sd_of_deltas": (
                round(statistics.pstdev(deltas), 6) if len(deltas) > 1 else None
            ),
            "n_direction_changes": sum(1 for d in deltas if d != 0),
            "expected_relation": EXPECTED_RELATION_BY_CONDITION.get(condition),
            "status": "MEASURED",
        })

    measured = [c for c in comparison if c["status"] == "MEASURED"]
    return {
        "metric": "multilingual_language_sensitivity",
        "schema_version": MULTILINGUAL_SCHEMA_VERSION,
        "status": "ok" if measured else "insufficient_design",
        "declared_conditions": list(LANGUAGE_CONDITIONS),
        "reference_condition": reference_condition,
        "conditions_observed": sorted(by_condition),
        "conditions_missing": sorted(set(LANGUAGE_CONDITIONS) - set(by_condition)),
        "n_items": len({str(r.get("item_id")) for r in validated}),
        "models": sorted({str(r["model"]) for r in validated if r.get("model")}),
        "condition_means": {
            condition: round(statistics.mean(values), 6)
            for condition, values in sorted(by_condition.items())
        },
        "comparison": comparison,
        "unknown_conditions_ignored": unknown,
        "expected_relations": dict(EXPECTED_RELATION_BY_CONDITION),
        "definitions": {
            "mean_delta_vs_reference": "mean of (condition score - reference score) "
                                      "over items present in both",
            "expected_relation": "not_invariant for the code-switched condition: a "
                                 "performance change there is the finding, not a failure",
        },
        "limits": [
            "With three conditions and paired items this is a small declared "
            "experiment, not a language ranking.",
            "A condition sharing no items with the reference is UNAVAILABLE, "
            "not a zero delta.",
            "Code-switching is expected to move the score, so its delta is a "
            "measurement and is never reported as a metamorphic violation.",
            "No finding is produced for conditions that were not measured; "
            "unknown conditions are listed and ignored.",
        ],
        "disclaimer": MULTILINGUAL_DISCLAIMER,
        "evidence": normalize_evidence(evidence),
        "paired": paired,
    }


__all__ = [
    "CODE_SWITCHED",
    "EXPECTED_RELATION_BY_CONDITION",
    "LANGUAGE_CONDITIONS",
    "MULTILINGUAL_DISCLAIMER",
    "MULTILINGUAL_SCHEMA_VERSION",
    "language_sensitivity_report",
]