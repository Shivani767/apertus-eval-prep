"""Release-gate report helpers."""
from __future__ import annotations

from typing import Any, Mapping

from apertus_eval_prep.release.gates import GateStatus, RELEASE_GATE_DISCLAIMER, evaluate_release_gates
from apertus_eval_prep.utils.pii import redact_text_for_report


def render_gate_markdown(decision: Mapping[str, Any]) -> str:
    lines = ["# Release-readiness gate", "", f"**Status:** `{decision.get('status', GateStatus.INCONCLUSIVE.value)}`", ""]
    reasons = decision.get("reasons") or []
    lines += [f"- {redact_text_for_report(str(reason))}" for reason in reasons] or ["- No failing rules were recorded."]
    lines += ["", RELEASE_GATE_DISCLAIMER]
    return "\n".join(lines) + "\n"


def apply_gate(metrics: dict[str, Any], rules: Mapping[str, Any] | None = None) -> dict[str, Any]:
    decision = evaluate_release_gates(metrics, rules)
    metrics["release_gate"] = decision
    return decision


__all__ = ["render_gate_markdown", "apply_gate"]
