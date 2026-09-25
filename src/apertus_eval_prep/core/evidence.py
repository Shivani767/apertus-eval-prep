"""Versioned evidence/provenance normalization helpers."""
from __future__ import annotations

from typing import Any, Mapping

EVIDENCE_MODES: tuple[str, ...] = (
    "MOCK", "SYNTHETIC", "LOCAL_REAL_MODEL", "EXTERNAL_PROVIDER",
    "HARDWARE_MEASURED", "HUMAN_VALIDATED", "MIXED", "UNKNOWN",
)
SYNTHETIC_EVIDENCE_MODES = frozenset({"MOCK", "SYNTHETIC"})
REAL_EVIDENCE_MODES = frozenset({
    "LOCAL_REAL_MODEL", "EXTERNAL_PROVIDER", "HARDWARE_MEASURED", "HUMAN_VALIDATED",
})


def _validate_consistency(data: Mapping[str, Any], mode: str) -> None:
    real = bool(data.get("real_model_execution"))
    external = bool(data.get("external_provider_execution"))
    hardware = bool(data.get("hardware_measured", False))
    human = bool(data.get("human_reviewed", False))
    if mode in SYNTHETIC_EVIDENCE_MODES and (real or external or hardware or human):
        raise ValueError(f"{mode} evidence cannot claim real or external model execution")
    if mode == "LOCAL_REAL_MODEL" and not real:
        raise ValueError("LOCAL_REAL_MODEL evidence requires real_model_execution=true")
    if mode == "EXTERNAL_PROVIDER" and not external:
        raise ValueError("EXTERNAL_PROVIDER evidence requires external_provider_execution=true")
    if mode == "HUMAN_VALIDATED" and not human:
        raise ValueError("HUMAN_VALIDATED evidence requires human_reviewed=true")
    if mode == "HARDWARE_MEASURED" and not hardware:
        raise ValueError("HARDWARE_MEASURED evidence requires hardware_measured=true")


def infer_evidence_mode(*, legacy_class: str | None = None, adapter_kind: str | None = None) -> str:
    """Infer only safe legacy modes; never label an old real run as measured."""
    if str(legacy_class or "").upper() in SYNTHETIC_EVIDENCE_MODES | {"DEMONSTRATION", "DEMO"}:
        return "MOCK" if str(legacy_class or "").upper() == "MOCK" else "SYNTHETIC"
    if str(legacy_class or "").upper() in {"HUMAN_VALIDATED"}:
        return "HUMAN_VALIDATED"
    if str(adapter_kind or "").lower() == "mock":
        return "MOCK"
    return "UNKNOWN"


def normalize_evidence(
    raw: Mapping[str, Any] | None = None,
    *, legacy_class: str | None = None, adapter_kind: str | None = None,
) -> dict[str, Any]:
    """Return a complete, versioned evidence record from new or legacy metadata."""
    data = dict(raw or {})
    mode = str(data.get("mode") or infer_evidence_mode(legacy_class=legacy_class, adapter_kind=adapter_kind)).upper()
    if mode not in EVIDENCE_MODES:
        raise ValueError(f"unsupported evidence mode: {mode!r}")
    synthetic = mode in SYNTHETIC_EVIDENCE_MODES
    runtime_environment = data.get("runtime_environment")
    if runtime_environment is not None:
        runtime_environment = str(runtime_environment).strip() or None
    known = data.get("known_limitations")
    limitations = [str(item).strip() for item in known if str(item).strip()] if isinstance(known, list) else []
    real_model_execution = bool(data.get("real_model_execution", mode == "LOCAL_REAL_MODEL"))
    external_provider_execution = bool(
        data.get("external_provider_execution", mode == "EXTERNAL_PROVIDER")
    )
    human_reviewed = bool(data.get("human_reviewed", mode == "HUMAN_VALIDATED"))
    _validate_consistency(
        {
            "real_model_execution": real_model_execution,
            "external_provider_execution": external_provider_execution,
            "hardware_measured": bool(data.get("hardware_measured", False)),
            "human_reviewed": human_reviewed,
        },
        mode,
    )
    return {
        "schema_version": "1.0",
        "mode": mode,
        "runtime_environment": runtime_environment,
        "real_model_execution": real_model_execution,
        "external_provider_execution": external_provider_execution,
        "hardware_measured": bool(data.get("hardware_measured", False)),
        "human_reviewed": human_reviewed,
        "pricing_source": str(data.get("pricing_source") or "unavailable"),
        "known_limitations": limitations or (["Synthetic evidence is not real model evidence."] if synthetic else []),
    }


def evidence_from_manifest(manifest: Mapping[str, Any] | None) -> dict[str, Any]:
    """Normalize new evidence or safely infer an old run's limited legacy state."""
    data = dict(manifest or {})
    model = data.get("model") if isinstance(data.get("model"), Mapping) else {}
    return normalize_evidence(
        data.get("evidence") if isinstance(data.get("evidence"), Mapping) else None,
        legacy_class=data.get("evidence_class"),
        adapter_kind=model.get("adapter_kind"),
    )


def evidence_metric_fields(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Canonical additive metrics fields for report and deployment consumers."""
    normalized = dict(evidence)
    mode = str(normalized.get("mode") or "UNKNOWN")
    return {
        "evidence": normalized,
        "evidence_mode": mode,
        "synthetic_or_mock": mode in SYNTHETIC_EVIDENCE_MODES,
    }


def evidence_for_spec_payload(
    raw: Mapping[str, Any] | None, *, legacy_class: str | None = None,
    adapter_kind: str | None = None,
) -> dict[str, Any]:
    """Normalize a spec evidence block, allowing safe legacy inference."""
    return normalize_evidence(raw, legacy_class=legacy_class, adapter_kind=adapter_kind)


__all__ = [
    "EVIDENCE_MODES", "SYNTHETIC_EVIDENCE_MODES", "REAL_EVIDENCE_MODES",
    "infer_evidence_mode",
    "normalize_evidence", "evidence_from_manifest", "evidence_metric_fields",
    "evidence_for_spec_payload",
]
