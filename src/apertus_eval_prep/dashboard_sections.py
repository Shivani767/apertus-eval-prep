"""Dashboard sections built from committed analysis artifacts.

The rule these sections follow is the one the rest of the platform already
uses: a section is rendered from an artifact that was committed, and an artifact
that does not exist is reported as *not generated* -- never zero-filled, never
back-filled with a plausible-looking number. A reader seeing an empty section can
tell the difference between "we measured nothing" and "the measurement is zero".

No experimental value is written into this module or into the frontend. Each
section is a thin, declarative projection of a committed artifact:

  reports/evaluation_sensitivity/*.json  -> evaluation_sensitivity
  reports/ranking_stability/*.json       -> ranking_stability
  reports/decision_stability/*.json      -> decision_stability
  reports/interactions/*.json            -> interaction_analysis
  reports/agent_regression/*.json        -> agent_reliability
  reports/scenario_coverage/*.json       -> scenario_coverage
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: section key -> (report directory, default artifact filename)
SECTION_ARTIFACTS: dict[str, tuple[str, str]] = {
    "evaluation_sensitivity": ("evaluation_sensitivity", "sensitivity.json"),
    "ranking_stability": ("ranking_stability", "ranking_stability.json"),
    "decision_stability": ("decision_stability", "decision_stability.json"),
    "interaction_analysis": ("interactions", "interactions.json"),
    "agent_reliability": ("agent_regression", "agent_regression.json"),
    "scenario_coverage": ("scenario_coverage", "scenario_coverage.json"),
}

#: Reported when a section has no committed artifact.
NOT_GENERATED_NOTE = (
    "No committed artifact for this section. Run the corresponding command to "
    "produce one; nothing is inferred or zero-filled here."
)


def _load(repo_root: Path, report_dir: str, filename: str) -> tuple[dict[str, Any] | None, str | None]:
    """Return (artifact, source path). Absent or unreadable -> (None, path)."""
    base = Path(repo_root) / "reports" / report_dir
    if not base.is_dir():
        return None, str(base)
    target = base / filename
    if not target.exists():
        existing = sorted(base.glob("*.json"))
        target = existing[0] if existing else None
    if target is None or not target.exists():
        return None, str(base)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"{target} (unreadable: {exc})"
    if not isinstance(payload, dict):
        return None, f"{target} (not a JSON object)"
    return payload, str(target)


def _sensitivity(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "uncertainty_scale": payload.get("uncertainty_scale"),
        "most_sensitive_factor": payload.get("most_sensitive_factor"),
        "factors": [
            {
                "factor": f.get("factor"),
                "status": f.get("status"),
                "absolute_delta": f.get("absolute_delta"),
                "relative_delta": f.get("relative_delta"),
                "confidence_interval_95": f.get("confidence_interval_95"),
                "standardized_effect_cohens_h": f.get("standardized_effect_cohens_h"),
                "esi": f.get("esi"),
                "esi_reason": f.get("esi_reason"),
            }
            for f in payload.get("factors") or []
        ],
        "definitions": payload.get("definitions"),
        "limits": payload.get("limits"),
        "disclaimer": payload.get("disclaimer"),
        "evidence": payload.get("evidence"),
    }


def _ranking_stability(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "ok",
        "mean_kendall_tau": payload.get("mean_kendall_tau"),
        "top_1_stability": payload.get("top_1_stability"),
        "top_k_stability": payload.get("top_k_stability"),
        "top_k": payload.get("k"),
        "rank_reversal_rate": payload.get("rank_reversal_rate"),
        "mean_pairwise_inversion_rate": payload.get("mean_pairwise_inversion_rate"),
        "valid_perturbations": payload.get("valid_perturbations"),
        "incomparable_perturbations": payload.get("incomparable_perturbations"),
        "composite_score": payload.get("composite_score"),
        "composite_rationale": payload.get("composite_rationale"),
        "disclaimer": payload.get("disclaimer"),
        "evidence": payload.get("evidence"),
    }


def _decision_stability(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "baseline_config": payload.get("baseline_config"),
        "baseline_decision": payload.get("baseline_decision"),
        "stability": payload.get("stability"),
        "stability_allowing_ties": payload.get("stability_allowing_ties"),
        "valid_configurations": payload.get("valid_configurations"),
        "same_decision": payload.get("same_decision"),
        "decision_reversals": payload.get("decision_reversals"),
        "tie_with_baseline": payload.get("tie_with_baseline"),
        "no_decision_configurations": payload.get("no_decision_configurations"),
        "invalid_configurations": payload.get("invalid_configurations"),
        "reversal_causes": payload.get("reversal_causes") or [],
        "reversal_cause_design": payload.get("reversal_cause_design"),
        "interpretation": payload.get("interpretation"),
        "disclaimer": payload.get("disclaimer"),
        "evidence": payload.get("evidence"),
    }


def _interaction_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    pairs = []
    for report in payload.get("pairs") or []:
        effects = report.get("effects") or {}
        pairs.append({
            "pair": report.get("pair"),
            "status": (report.get("decomposition") or {}).get("status"),
            "main_effects": [
                {
                    "factor": (effects.get(term) or {}).get("factor"),
                    "omega2_pct": (effects.get(term) or {}).get("omega2_pct"),
                    "p_value": (effects.get(term) or {}).get("p_value"),
                    "p_value_corrected": (effects.get(term) or {}).get("p_value_corrected"),
                    "status": (effects.get(term) or {}).get("status"),
                }
                for term in ("factor_a", "factor_b")
            ],
            "interaction": {
                "omega2_pct": (effects.get("interaction") or {}).get("omega2_pct"),
                "f": (effects.get("interaction") or {}).get("f"),
                "p_value": (effects.get("interaction") or {}).get("p_value"),
                "p_value_corrected": (effects.get("interaction") or {}).get("p_value_corrected"),
                "confidence_interval_95_pct": (effects.get("interaction") or {}).get("bootstrap_ci95_pct"),
                "status": (effects.get("interaction") or {}).get("status"),
            },
        })
    return {
        "status": payload.get("status"),
        "design_kind": payload.get("design_kind"),
        "design_note": payload.get("design_note"),
        "n_pairs_measured": payload.get("n_pairs_measured"),
        "n_pairs_requested": payload.get("n_pairs_requested"),
        "n_effects_tested": payload.get("n_effects_tested"),
        "multiple_comparison_correction": payload.get("multiple_comparison_correction"),
        "unavailable_pairs": payload.get("unavailable_pairs") or [],
        "pairs": pairs,
        "limits": payload.get("limits"),
        "disclaimer": payload.get("disclaimer"),
        "evidence": payload.get("evidence"),
    }


def _agent_reliability(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload.get("comparison") or {}
    gate = payload.get("gate") or {}
    metrics = comparison.get("metrics") or {}
    headline = (
        "task_success", "tool_selection", "tool_argument_correctness",
        "groundedness", "recovery", "latency_ms_mean", "total_tokens_mean",
        "unsafe_action_rate",
    )
    return {
        "status": "ok",
        "baseline": comparison.get("baseline"),
        "candidate": comparison.get("candidate"),
        "metrics": [
            {
                "metric": name,
                "baseline": (metrics.get(name) or {}).get("baseline"),
                "candidate": (metrics.get(name) or {}).get("candidate"),
                "delta": (metrics.get(name) or {}).get("delta"),
                "direction": (metrics.get(name) or {}).get("direction"),
                "status": (metrics.get(name) or {}).get("status"),
            }
            for name in headline if name in metrics
        ],
        "regressions": comparison.get("regressions") or [],
        "improvements": comparison.get("improvements") or [],
        "not_comparable": comparison.get("not_comparable") or [],
        "gate": {
            "present": bool(gate),
            "result_type": gate.get("result_type"),
            "status": gate.get("status"),
            "n_passed": gate.get("n_passed"),
            "n_failed": gate.get("n_failed"),
            "n_inconclusive": gate.get("n_inconclusive"),
            "gates": gate.get("gates") or [],
            "disclaimer": gate.get("disclaimer"),
        } if gate else {"present": False},
        "gate_note": payload.get("gate_note"),
        "limits": comparison.get("limits"),
        "evidence": gate.get("evidence") or comparison.get("evidence"),
    }


def _scenario_coverage(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "ok",
        "taxonomy_size": payload.get("taxonomy_size"),
        "declared": payload.get("declared_scenarios"),
        "not_applicable": payload.get("not_applicable_scenarios"),
        "tested": payload.get("executed_scenarios"),
        "passed": payload.get("succeeded_scenarios"),
        "failed": payload.get("failed_scenarios"),
        "executed_without_signal": payload.get("executed_without_signal"),
        "untested": payload.get("untested_scenarios") or [],
        "failed_scenario_ids": payload.get("failed_scenario_ids") or [],
        "count_coverage": payload.get("count_coverage"),
        "execution_coverage": payload.get("execution_coverage"),
        "success_rate_of_executed": payload.get("success_rate_of_executed"),
        "definitions": payload.get("definitions"),
        "limits": payload.get("limits"),
    }


_PROJECTIONS = {
    "evaluation_sensitivity": _sensitivity,
    "ranking_stability": _ranking_stability,
    "decision_stability": _decision_stability,
    "interaction_analysis": _interaction_analysis,
    "agent_reliability": _agent_reliability,
    "scenario_coverage": _scenario_coverage,
}


def build_analysis_sections(repo_root: Path | str) -> dict[str, Any]:
    """Project every committed analysis artifact into a dashboard section.

    A section whose artifact is absent, unreadable or not a JSON object is
    reported with ``status: not_generated`` and the path that was expected. It
    is never replaced with zeros or an empty-but-plausible reading, because a
    dashboard that cannot tell "not measured" from "measured zero" is worse
    than one that shows nothing.
    """
    root = Path(repo_root)
    sections: dict[str, Any] = {}
    for key, (report_dir, filename) in SECTION_ARTIFACTS.items():
        payload, source = _load(root, report_dir, filename)
        if payload is None:
            sections[key] = {
                "status": "not_generated",
                "source": source,
                "expected_artifact": f"reports/{report_dir}/{filename}",
                "note": NOT_GENERATED_NOTE,
            }
            continue
        section = _PROJECTIONS[key](payload)
        section["status"] = section.get("status") or payload.get("status") or "ok"
        section["source"] = source
        section["provenance"] = "read from a committed analysis artifact; not recomputed here"
        sections[key] = section
    return sections


__all__ = ["NOT_GENERATED_NOTE", "SECTION_ARTIFACTS", "build_analysis_sections"]

