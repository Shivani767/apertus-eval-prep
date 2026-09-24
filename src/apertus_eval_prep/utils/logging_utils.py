"""Structured, secret-safe logging for the platform layer.

Every record is redacted through the PII policy before it is emitted. Raw
prompt/output text may be retained only when a caller explicitly passes
``allow_raw=True``, and credential-shaped values are still always scrubbed.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any, TextIO

from apertus_eval_prep.utils.pii import (
    DEFAULT_POLICY,
    RedactionPolicy,
    redact_for_artifact,
    redact_structure,
    redact_text,
)

LEVELS = {"debug": 10, "info": 20, "warning": 30, "error": 40}


class StructuredLogger:
    """Minimal structured logger: one JSON object (or one line) per event."""

    def __init__(
        self,
        name: str,
        *,
        stream: TextIO | None = None,
        json_mode: bool = True,
        policy: RedactionPolicy = DEFAULT_POLICY,
        level: str = "info",
    ) -> None:
        if level not in LEVELS:
            raise ValueError(f"level must be one of {sorted(LEVELS)}")
        self.name = name
        self.stream = stream if stream is not None else sys.stderr
        self.json_mode = json_mode
        self.policy = policy
        self.level = level

    def _enabled(self, level: str) -> bool:
        return LEVELS[level] >= LEVELS[self.level]

    def event(self, event: str, *, level: str = "info", allow_raw: bool = False, **fields: Any) -> None:
        """Emit one structured event; raw mode still scrubs credentials."""
        if level not in LEVELS:
            raise ValueError(f"level must be one of {sorted(LEVELS)}")
        if not self._enabled(level):
            return
        safe_fields: dict[str, Any]
        if allow_raw:
            safe_fields = redact_for_artifact(fields)
        else:
            safe_fields = redact_structure(fields, self.policy)
        if self.json_mode:
            record = {
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "level": level,
                "logger": self.name,
                "event": event,
                **{k: v for k, v in safe_fields.items() if v is not None},
            }
            self.stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        else:
            rendered = " ".join(f"{k}={v!r}" for k, v in safe_fields.items() if v is not None)
            self.stream.write(f"[{level}] {self.name}: {event} {rendered}".rstrip() + "\n")
        self.stream.flush()

    def info(self, event: str, **fields: Any) -> None:
        self.event(event, level="info", **fields)

    def warning(self, event: str, **fields: Any) -> None:
        self.event(event, level="warning", **fields)

    def error(self, event: str, **fields: Any) -> None:
        self.event(event, level="error", **fields)

    def debug(self, event: str, **fields: Any) -> None:
        self.event(event, level="debug", **fields)


def get_logger(name: str, *, json_mode: bool = True, level: str = "info") -> StructuredLogger:
    """Factory used by modules (no hidden global handler configuration)."""
    return StructuredLogger(name, json_mode=json_mode, level=level)


def safe_message(text: str, policy: RedactionPolicy = DEFAULT_POLICY) -> str:
    """Redact a free-form message before it is embedded in an error or report."""
    return redact_text(text, policy)
