"""Fail if a credential is committed to the repository.

Secrets belong in environment variables, Colab secrets or a local ignored file, never
in a tracked file. This test scans tracked text files for high-confidence credential
shapes and reports file names only, so a failure never echoes the value into CI logs.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: High-confidence credential shapes: prefix plus a long opaque body.
CREDENTIAL_PATTERNS: dict[str, re.Pattern[str]] = {
    "hugging_face_token": re.compile(r"hf_[A-Za-z0-9]{30,}"),
    "openai_like_key": re.compile(r"sk-[A-Za-z0-9]{32,}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "slack_token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    "private_key_block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "slippy_bearer": re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-._~+/=]{24,}"),
}

#: Binary or generated paths that carry no source to review.
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".pt", ".bin", ".safetensors"}


def tracked_text_files() -> list[Path]:
    """Every tracked file that is plain text we can scan."""
    names = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True, text=True
    ).stdout.split("\0")
    paths = []
    for name in names:
        if not name or Path(name).suffix.lower() in SKIP_SUFFIXES:
            continue
        path = ROOT / name
        if path.is_file():
            paths.append(path)
    return paths


def test_no_credential_is_committed():
    """Scan tracked files; report names only so a leak is not repeated in the log."""
    findings: list[str] = []
    for path in tracked_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for label, pattern in CREDENTIAL_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{path.relative_to(ROOT)}: {label}")
    assert not findings, "possible committed credential(s): " + "; ".join(findings)
