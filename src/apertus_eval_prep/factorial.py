"""Factorial interaction analysis: report what a design can and cannot support.

OFAT data and factorial data answer different questions, and conflating them
is the most common way an interaction study produces a confident wrong answer.
An OFAT design varies one factor at a time from a shared control, so the cell
where *both* factors differ was never run. A main effect measured that way is
an average over levels of the other factor, and any interaction between them
is structurally unmeasurable -- not "small", not "not found", *unmeasured*.

This module makes that distinction explicit in the artifact rather than leaving
a reader to infer it from a p-value:

* ``design_kind`` is ``ofat``, ``factorial`` or ``partially_crossed``;
* every pair that could not be decomposed carries ``status: UNAVAILABLE`` and
  a reason naming the design limitation, not a number;
* when several pairs are screened at once, p-values are corrected with
  ``stats.holm_bonferroni`` so a screen cannot manufacture a finding.

Main effects, interaction, effect size, uncertainty and the corrected
p-value are reported as separate fields and never merged into a single
verdict. Statistical significance is explicitly not presented as practical
importance.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from apertus_eval_prep.core.evidence import normalize_evidence
from apertus_eval_prep.stats import benjamini_hochberg, holm_bonferroni
from apertus_eval_prep.variance import (
    factorial_diagnostics,
    factorial_variance_decomposition,
    interaction_screen,
)

INTERACTION_SCHEMA_VERSION = "1.0"

INTERACTION_DISCLAIMER = (
    "Interaction estimates describe a declared experimental design. An "
    "unavailable interaction is a property of that design, not evidence that "
    "the factors do not interact. These are engineering diagnostics and are "
    "not a causal claim, a certification, or production approval."
)

OFAT = "ofat"
FACTORIAL = "factorial"
PARTIALLY_CROSSED = "partially_crossed"


def classify_design(rows: Sequence[Mapping[str, Any]], pairs: Sequence[tuple[str, str]]) -> str:
    """Label the design from the observed cells, not from what it was called.

    A pair is crossed when every level combination of its two factors was
    observed with at least one scored replicate. Only when *every* requested
    pair is crossed is the design a factorial one.
    """
    crossed_flags = []
    for factor_a, factor_b in pairs:
        screen = interaction_screen(rows_for_pair(rows, factor_a, factor_b), factor_a, factor_b)
        crossed_flags.append(bool(screen["crossed_design"]))
    if crossed_flags and all(crossed_flags):
        return FACTORIAL
    if not any(crossed_flags):
        return OFAT
    return PARTIALLY_CROSSED


def rows_for_pair(
    rows: Sequence[Mapping[str, Any]], factor_a: str, factor_b: str
) -> list[dict[str, Any]]:
    """Keep only rows that actually declare BOTH factors of the pair.

    ``interaction_screen`` reads factor levels with ``.get()``, so a row that
    does not mention a factor would otherwise contribute a phantom ``"None"``
    level and quietly create a cell that was never run. Excluding those rows
    keeps the design exactly as declared.
    """
    return [dict(row) for row in rows if factor_a in row and factor_b in row]


def _correction(method: str, p_values: Sequence[float]) -> list[float | None]:
    """Apply a declared multiple-comparison correction, preserving positions."""
    if method == "holm_bonferroni":
        corrected = holm_bonferroni(p_values)
    elif method == "benjamini_hochberg":
        corrected = benjamini_hochberg(p_values)
    elif method in ("none", ""):
        corrected = list(p_values)
    else:
        raise ValueError(
            f"unsupported correction {method!r}; use none, holm_bonferroni or benjamini_hochberg"
        )
    return [None if value is None else value for value in corrected]


def analyse_interactions(
    rows: Sequence[Mapping[str, Any]],
    pairs: Sequence[tuple[str, str]],
    *,
    correction: str = "holm_bonferroni",
    n_boot: int = 0,
    seed: int = 0,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Screen factor pairs for main effects and interaction, or say why not.

    ``rows`` are already-scored observations carrying the factor columns and a
    numeric ``score`` for each pair. Nothing is measured here and no cell is
    imputed: an unmeasured cell makes the design unbalanced, which is reported
    as a refusal rather than papered over.
    """
    materialised = [dict(row) for row in rows]
    design_kind = classify_design(materialised, pairs)

    pair_reports: list[dict[str, Any]] = []
    for factor_a, factor_b in pairs:
        pair_rows = rows_for_pair(materialised, factor_a, factor_b)
        dropped = len(materialised) - len(pair_rows)
        decomposition = factorial_variance_decomposition(
            pair_rows, factor_a, factor_b, n_boot=n_boot, seed=seed
        )
        pair_reports.append({
            "pair": [factor_a, factor_b],
            "n_rows_considered": len(pair_rows),
            "n_rows_without_both_factors": dropped,
            "screen": interaction_screen(pair_rows, factor_a, factor_b),
            "diagnostics": factorial_diagnostics(pair_rows, factor_a, factor_b),
            "decomposition": decomposition,
            "_raw_p": {
                term: (decomposition.get("f_tests") or {}).get(term, {}).get("p_value")
                for term in ("factor_a", "factor_b", "interaction")
            },
        })

    measured = [r for r in pair_reports if r["decomposition"].get("status") == "MEASURED"]
    flat: list[float] = []
    slots: list[tuple[dict[str, Any], str]] = []
    for report in measured:
        for term, value in report["_raw_p"].items():
            if value is not None:
                flat.append(value)
                slots.append((report, term))
    corrected_values = _correction(correction, flat)
    for (report, term), value in zip(slots, corrected_values):
        report.setdefault("_corrected_p", {})[term] = value
    n_tests = len(flat)

    # The correction is only meaningful across the terms actually tested, so it
    # is reported next to the count it was computed over.
    for report in pair_reports:
        report.pop("_raw_p", None)
        decomposition = report["decomposition"]
        usable = decomposition.get("f_tests") or {}
        fractions = decomposition.get("effect_sizes_omega2_pct") or {}
        bootstrap = decomposition.get("bootstrap_ci95") or {}
        report["effects"] = {
            term: {
                "factor": (
                    report["pair"][0] if term == "factor_a"
                    else report["pair"][1] if term == "factor_b"
                    else "interaction"
                ),
                "kind": "interaction" if term == "interaction" else "main_effect",
                "omega2_pct": fractions.get(term),
                "variance_fraction": (decomposition.get("variance_fractions") or {}).get(term),
                "f": usable.get(term, {}).get("f"),
                "p_value": usable.get(term, {}).get("p_value"),
                "p_value_corrected": report.get("_corrected_p", {}).get(term),
                "status": usable.get(term, {}).get("status", "UNAVAILABLE"),
                "reason": usable.get(term, {}).get("reason"),
                "bootstrap_ci95_pct": bootstrap.get(term),
            }
            for term in ("factor_a", "factor_b", "interaction")
        }
        report.pop("_corrected_p", None)

    measured_count = len(measured)
    return {
        "metric": "factorial_interaction_analysis",
        "schema_version": INTERACTION_SCHEMA_VERSION,
        "status": "ok" if measured else "insufficient_design",
        "design_kind": design_kind,
        "design_note": _design_note(design_kind),
        "n_observations": len(materialised),
        "n_pairs_requested": len(pairs),
        "n_pairs_measured": measured_count,
        "n_effects_tested": n_tests,
        "multiple_comparison_correction": correction,
        "pairs": pair_reports,
        "unavailable_pairs": [
            r["pair"] for r in pair_reports if r["decomposition"].get("status") != "MEASURED"
        ],
        "interpretation": _interpretation(design_kind, pair_reports, n_tests),
        "limits": [
            "An UNAVAILABLE pair is a design limitation, not a null result.",
            "p-values describe detectability at this sample size; omega-squared "
            "describes magnitude. Neither alone is practical importance.",
            "These estimates describe the evaluated configurations only and do "
            "not extrapolate to unevaluated ones.",
        ],
        "disclaimer": INTERACTION_DISCLAIMER,
        "evidence": normalize_evidence(evidence),
    }


def _design_note(design_kind: str) -> str:
    if design_kind == OFAT:
        return (
            "OFAT: one factor varies at a time from a shared control, so cells "
            "where two factors differ were never run. Main effects are averages "
            "over the other factor and interactions are structurally "
            "unmeasurable."
        )
    if design_kind == FACTORIAL:
        return (
            "Factorial: every requested factor pair was crossed, so main "
            "effects and their interaction are jointly estimable."
        )
    return (
        "Partially crossed: some requested pairs were measured and others were "
        "not. Read the measured and unavailable pairs separately; they are not "
        "interchangeable."
    )


def _interpretation(
    design_kind: str, reports: Sequence[Mapping[str, Any]], n_tests: int
) -> str:
    if not reports:
        return "No factor pairs were requested."
    measured = [r for r in reports if r["decomposition"].get("status") == "MEASURED"]
    if not measured:
        return (
            f"Design kind {design_kind}: no requested pair could be decomposed, "
            "so no main effect or interaction estimate is reported."
        )
    interactions = [
        r for r in measured if r["effects"]["interaction"]["omega2_pct"] is not None
    ]
    if not interactions:
        return (
            f"Design kind {design_kind}: {len(measured)} pair(s) decomposed; "
            "no interaction estimate was available."
        )
    largest = max(interactions, key=lambda r: r["effects"]["interaction"]["omega2_pct"] or 0.0)
    factor_a, factor_b = largest["pair"]
    effect = largest["effects"]["interaction"]
    return (
        f"Design kind {design_kind}: {len(measured)} of {len(reports)} pair(s) "
        f"decomposed across {n_tests} effect test(s). Largest interaction is "
        f"{factor_a}x{factor_b} at omega^2={effect['omega2_pct']}% "
        f"(p={effect['p_value']}, corrected p={effect['p_value_corrected']})."
    )


__all__ = [
    "FACTORIAL",
    "INTERACTION_DISCLAIMER",
    "INTERACTION_SCHEMA_VERSION",
    "OFAT",
    "PARTIALLY_CROSSED",
    "analyse_interactions",
    "classify_design",
]
