"""Typed exceptions with stable machine-readable codes.

Every platform error carries a ``code`` so callers (CLI, CI, gates) can branch on
the failure class without string matching, and a ``details`` mapping for
structured, already-redacted context.
"""

from __future__ import annotations

from typing import Any


class PlatformError(Exception):
    """Base class for every platform-layer error."""

    code = "platform_error"

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class ConfigError(PlatformError):
    """Malformed or contradictory configuration (YAML shape, unknown factor, ...)."""

    code = "config_error"


class SchemaValidationError(ConfigError):
    """A schema object failed validation; ``field`` names the offending path."""

    code = "schema_validation_error"

    def __init__(self, field: str, message: str, **details: Any) -> None:
        super().__init__(f"{field}: {message}", field=field, **details)
        self.field = field


class DatasetError(PlatformError):
    """Dataset missing, empty, or unreadable."""

    code = "dataset_error"


class ArtifactError(PlatformError):
    """Artifact directory/file problem (write failure, malformed artifact)."""

    code = "artifact_error"


class ArtifactExistsError(ArtifactError):
    """A run directory already exists — runs are never overwritten silently."""

    code = "artifact_exists"


class AdapterError(PlatformError):
    """Model adapter failed (transport, protocol, invalid response)."""

    code = "adapter_error"


class AdapterTimeoutError(AdapterError):
    """Adapter exceeded its deadline; counted as an infrastructure failure."""

    code = "adapter_timeout"


class AdapterResponseError(AdapterError):
    """Adapter returned a response that violates the expected contract."""

    code = "adapter_response_error"


class GateConfigError(PlatformError):
    """Release-gate specification is malformed."""

    code = "gate_config_error"


class SafetyConfigError(PlatformError):
    """Safety taxonomy/test-case configuration is malformed."""

    code = "safety_config_error"
