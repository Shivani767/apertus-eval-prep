"""Tool trace validation and episode reliability metrics."""
from __future__ import annotations

from typing import Any, Mapping, Sequence


def validate_tool_call(call: Mapping[str, Any], tools: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    name = str(call.get("name") or call.get("tool_name") or "")
    spec = next((item for item in tools if str(item.get("name")) == name), None)
    if spec is None:
        return {"valid": False, "reason": "unknown_tool", "tool": name}
    schema = spec.get("input_schema") or spec.get("parameters") or {}
    required = schema.get("required", []) if isinstance(schema, Mapping) else []
    args = call.get("arguments") if isinstance(call.get("arguments"), Mapping) else {}
    missing = [str(key) for key in required if key not in args]
    return {"valid": not missing, "reason": "missing_required_arguments" if missing else "ok",
            "tool": name, "missing": missing}


def _actual_tools(traces: Sequence[Mapping[str, Any]]) -> list[str]:
    return [str(trace.get("tool_name") or trace.get("name") or "") for trace in traces]


def _unnecessary_calls(actual: Sequence[str], expected: Sequence[str]) -> int:
    """Count actual calls not consumed by the expected order-preserving plan."""
    remaining = list(expected)
    unnecessary = 0
    for name in actual:
        if name in remaining:
            remaining.remove(name)
        else:
            unnecessary += 1
    return unnecessary


def score_tool_sequence(traces: Sequence[Mapping[str, Any]], expected: Sequence[str]) -> dict[str, Any]:
    actual = _actual_tools(traces)
    expected = [str(item) for item in expected]
    prefix = 0
    for left, right in zip(actual, expected):
        if left != right:
            break
        prefix += 1
    return {"valid": actual == expected, "actual": actual, "expected": expected,
            "matched_prefix": prefix, "sequence_length": len(actual),
            "missing": expected[len(actual):]}


def score_tool_use(traces: Sequence[Mapping[str, Any]], *, expected_tools: Sequence[str] = ()) -> dict[str, Any]:
    valid = sum(bool(trace.get("schema_valid", trace.get("valid", True))) for trace in traces)
    sequence = score_tool_sequence(traces, expected_tools)
    unnecessary = _unnecessary_calls(sequence["actual"], sequence["expected"])
    actual_count = len(sequence["actual"])
    efficiency = 1.0 if not actual_count else max(0.0, 1.0 - unnecessary / max(1, actual_count))
    return {"tool_call_count": actual_count, "schema_validity_rate": valid / actual_count if actual_count else None,
            "sequence_validity_rate": 1.0 if sequence["valid"] else 0.0,
            "sequence": sequence, "unnecessary_tool_calls": unnecessary,
            "unnecessary_tool_call_count": unnecessary,
            "missing_tool_calls": len(sequence["missing"]), "tool_call_efficiency": efficiency,
            "recovery_success_rate": None}


def score_recovery(traces: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    failures = [trace for trace in traces if trace.get("error_type") or trace.get("result_status") not in (None, "ok", "success")]
    recovered = [trace for trace in traces[1:] if trace.get("recovered") and not trace.get("error_type")]
    return {"failed_steps": len(failures), "recovered_steps": len(recovered),
            "recovery_attempts": sum(int(trace.get("retry_count") or 0) for trace in traces),
            "recovery_success_rate": len(recovered) / len(failures) if failures else None,
            "recovery_observed": bool(failures)}


def simulate_tool_result(
    call: Mapping[str, Any], validation: Mapping[str, Any], *, episode_id: str, step: int,
    metadata: Mapping[str, Any] | None = None, previous_traces: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Deterministically execute a declared offline mock tool for evaluation traces."""
    metadata = dict(metadata or {})
    name = str(call.get("name") or call.get("tool_name") or "")
    previous_failures = sum(
        1 for trace in previous_traces
        if str(trace.get("tool_name")) == name and trace.get("error_type")
    )
    failure_mode = metadata.get("tool_failure")
    if not bool(validation.get("valid")):
        return {"result_status": "error", "error_type": str(validation.get("reason") or "schema_validation_error"),
                "retry_count": previous_failures, "recovered": False,
                "result": {"tool": name, "message": "tool arguments failed schema validation"}}
    if failure_mode in {"timeout", "error"} and previous_failures == 0:
        status = "timeout" if failure_mode == "timeout" else "error"
        return {"result_status": status, "error_type": failure_mode,
                "retry_count": previous_failures, "recovered": False,
                "result": {"tool": name, "message": f"simulated {failure_mode}"}}
    return {"result_status": "ok", "error_type": None,
            "retry_count": previous_failures, "recovered": previous_failures > 0,
            "result": {"tool": name, "message": "offline mock tool result", "episode_id": episode_id, "step": step}}


__all__ = ["validate_tool_call", "score_tool_sequence", "score_tool_use", "score_recovery", "simulate_tool_result"]
