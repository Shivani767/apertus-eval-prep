"""PII / secret detection and redaction for logs, artifacts and reports.

Design notes
------------
* Redaction is a *reduction*, not a guarantee: pattern matching finds common PII
  and credential shapes, it cannot prove a payload is anonymous. Reports say so.
* Two modes exist: ``redact_text`` (replacement) and ``detect_sensitive``
  (counts only). Detection is used to flag ``privacy_sensitive_output``
  failures without destroying the evidence.
* Structure-aware redaction also scrubs sensitive *keys*
  (``authorization``, ``api_key``, ``password``, ...) so a config dump can never
  leak a credential even if the value does not match a value pattern.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

#: Substrings that mark a mapping key as sensitive (case-insensitive, substring
#: match on the normalised key).
SENSITIVE_KEY_MARKERS: tuple[str, ...] = (
    "password",
    "passwd",
    "secret",
    "api_key",
    "apikey",
    "access_key",
    "authorization",
    "auth_token",
    "credential",
    "private_key",
    "client_secret",
    "session_cookie",
)
SENSITIVE_EXACT_KEYS: frozenset[str] = frozenset({
    "token", "access_token", "refresh_token", "id_token", "bearer", "jwt", "cookie",
})

REDACTED_FIELD = "[REDACTED_FIELD]"


def _placeholder(pattern: str) -> str:
    return f"[REDACTED:{pattern}]"


#: Ordered pattern book. Order matters: specific credential shapes run before
#: generic digit patterns so the placeholder names stay informative.
PATTERN_BOOK: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
    (
        "credential",
        re.compile(
            r"(?i)\b(?:sk|pk|rk|hf_|ghp|gho|github_pat|xox[baprs]|AKIA|AIza)[A-Za-z0-9_\-]{12,}\b"
        ),
    ),
    ("credential", re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9\-._~+/=]{12,}")),
    (
        "credential_assignment",
        re.compile(
            r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?key|client[_-]?secret|token)"
            r"\s*[:=]\s*[^\s,;\"']{6,}"
        ),
    ),
    (
        "url_credentials",
        re.compile(r"(?i)https?://[^\s/:@]+:[^\s/@]+@"),
    ),
    (
        "url_credentials",
        re.compile(r"(?i)([?&](?:api[_-]?key|access[_-]?key|token|secret|password)=)[^&#\s]+"),
    ),
    ("ipv4", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    (
        "phone",
        re.compile(
            r"(?<![\d])(?:\+\d{1,3}[ .\-]?)?(?:\(\d{2,4}\)[ .\-]?|\d{2,4}[ .\-])"
            r"\d{3,4}[ .\-]?\d{0,4}(?![\d])"
        ),
    ),
    # A digit run touching a decimal point is a number, not a card. Without the "."
    # in the boundary classes a metric such as 0.4736842105263158 (16 fractional
    # digits) is redacted as card_like, and reports lose their own headline metric.
    ("card_like", re.compile(r"(?<![\d.])(?:\d[ \-]?){13,19}(?![\d.])")),
)


@dataclass(frozen=True)
class RedactionPolicy:
    """Which pattern families to act on. Defaults redact everything we detect."""

    enabled: bool = True
    families: tuple[str, ...] = (
        "email",
        "credential",
        "credential_assignment",
        "url_credentials",
        "ipv4",
        "phone",
        "card_like",
    )

    def active(self, family: str) -> bool:
        return self.enabled and family in self.families


DEFAULT_POLICY = RedactionPolicy()
#: Credential-only policy used for provenance/config artifacts. PII redaction
#: remains configurable for prompts and model outputs, but credentials are never
#: persisted merely because an operator set ``pii_redaction: false``.
ARTIFACT_POLICY = RedactionPolicy(
    enabled=True,
    families=("credential", "credential_assignment", "url_credentials"),
)
#: Report policy adds textual PII redaction but omits the broad phone heuristic:
#: latency/token measurements can otherwise be mistaken for phone numbers.
REPORT_POLICY = RedactionPolicy(
    enabled=True,
    families=(
        "email", "credential", "credential_assignment", "url_credentials", "card_like",
    ),
)


@dataclass
class RedactionReport:
    """Counts of what was found/redacted; safe to log and store."""

    counts: dict[str, int] = field(default_factory=dict)
    enabled: bool = True

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def to_dict(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "total": self.total, "counts": dict(self.counts)}


def _iter_active(policy: RedactionPolicy) -> tuple[tuple[str, re.Pattern[str]], ...]:
    return tuple((name, rx) for name, rx in PATTERN_BOOK if policy.active(name))


def detect_sensitive(text: str, policy: RedactionPolicy = DEFAULT_POLICY) -> dict[str, int]:
    """Count matches per family without modifying the text."""
    if not policy.enabled or not text:
        return {}
    counts: dict[str, int] = {}
    for name, rx in _iter_active(policy):
        found = len(rx.findall(text))
        if found:
            counts[name] = counts.get(name, 0) + found
    return counts


def redact_text(
    text: str,
    policy: RedactionPolicy = DEFAULT_POLICY,
    report: RedactionReport | None = None,
) -> str:
    """Replace detected PII/credential shapes with typed placeholders."""
    if not policy.enabled or not text:
        return text
    out = text
    for name, rx in _iter_active(policy):
        out, n = rx.subn(_placeholder(name), out)
        if n and report is not None:
            report.counts[name] = report.counts.get(name, 0) + n
    return out


def is_sensitive_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "_", str(key).lower())
    # Environment-variable references are configuration, not credentials.
    if normalized.endswith(("_env", "_env_var", "_environment_variable")):
        return False
    if normalized in SENSITIVE_EXACT_KEYS:
        return True
    return any(marker in normalized for marker in SENSITIVE_KEY_MARKERS)


def redact_structure(
    value: Any,
    policy: RedactionPolicy = DEFAULT_POLICY,
    report: RedactionReport | None = None,
    *,
    max_depth: int = 12,
) -> Any:
    """Recursively redact strings and sensitive mapping keys."""
    if max_depth < 0:
        return "[REDACTED_DEPTH_LIMIT]"
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            text_key = str(key)
            if is_sensitive_key(text_key):
                out[text_key] = REDACTED_FIELD
                if report is not None:
                    report.counts["sensitive_field"] = report.counts.get("sensitive_field", 0) + 1
                continue
            out[text_key] = redact_structure(item, policy, report, max_depth=max_depth - 1)
        return out
    if isinstance(value, (list, tuple)):
        return [redact_structure(v, policy, report, max_depth=max_depth - 1) for v in value]
    if isinstance(value, str):
        return redact_text(value, policy, report)
    return value


def redact_for_artifact(value: Any, *, max_depth: int = 12) -> Any:
    """Redact credentials and credential-shaped assignments for persistence.

    This is intentionally stricter than the configurable prompt/output policy:
    disabling PII redaction must never turn artifact serialization into a secret
    persistence mechanism.
    """
    return redact_structure(value, ARTIFACT_POLICY or DEFAULT_POLICY, max_depth=max_depth)


def redact_text_for_artifact(text: str | None) -> str:
    """Redact credentials before persistence without altering numeric metrics."""
    if text is None:
        return ""
    return redact_text(str(text), ARTIFACT_POLICY)


def redact_text_for_report(text: str | None) -> str:
    """Redact report text while preserving measured numeric metric values."""
    if text is None:
        return ""
    return redact_text(str(text), REPORT_POLICY)


def sanitize_for_report(
    text: str | None,
    policy: RedactionPolicy = DEFAULT_POLICY,
    *,
    max_chars: int = 400,
) -> str:
    """Redact then truncate; ``None`` becomes an explicit empty marker."""
    if text is None:
        return ""
    return truncate_text(redact_text(text, policy), max_chars)


def truncate_text(text: str, max_chars: int) -> str:
    """Truncate with an explicit, auditable marker (never silent)."""
    if max_chars < 0:
        raise ValueError("max_chars must be >= 0")
    if len(text) <= max_chars:
        return text
    removed = len(text) - max_chars
    return f"{text[:max_chars]}… [truncated {removed} chars]"
