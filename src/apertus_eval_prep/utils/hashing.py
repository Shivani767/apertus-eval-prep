"""Deterministic hashing helpers for configs, datasets, prompts and templates.

Everything here is dependency-free and process-stable: the same Python object
always produces the same digest, in any process, on any platform. That property
is what makes run manifests auditable.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

DEFAULT_HASH_LENGTH = 16
_CHUNK_SIZE = 1 << 20


def _normalize(obj: Any) -> Any:
    """Reduce arbitrary objects to JSON-compatible, order-stable primitives."""
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return _normalize(dataclasses.asdict(obj))
    if isinstance(obj, Mapping):
        return {str(k): _normalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_normalize(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        items = [_normalize(v) for v in obj]
        return sorted(items, key=canonical_json)
    if isinstance(obj, Path):
        return str(obj)
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        return _normalize(to_dict())
    return str(obj)


def canonical_json(obj: Any) -> str:
    """Compact, key-sorted JSON string used as the canonical hash payload."""
    return json.dumps(
        _normalize(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def stable_hash(obj: Any, *, length: int = DEFAULT_HASH_LENGTH) -> str:
    """SHA-256 (truncated) digest of the canonical form of ``obj``."""
    if length <= 0:
        raise ValueError("length must be a positive integer")
    digest = hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()
    return digest[:length]


def hash_text(text: str, *, length: int = DEFAULT_HASH_LENGTH) -> str:
    """Digest of a text payload (prompt templates, rendered prompts)."""
    if not isinstance(text, str):
        raise TypeError("hash_text expects a str")
    if length <= 0:
        raise ValueError("length must be a positive integer")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def hash_bytes(data: bytes, *, length: int = DEFAULT_HASH_LENGTH) -> str:
    """Digest of a raw byte payload."""
    if length <= 0:
        raise ValueError("length must be a positive integer")
    return hashlib.sha256(data).hexdigest()[:length]


def hash_file(path: str | Path, *, length: int = DEFAULT_HASH_LENGTH) -> str:
    """Streaming digest of a file (dataset locks, prompt packs, configs)."""
    if length <= 0:
        raise ValueError("length must be a positive integer")
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while chunk := fh.read(_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()[:length]


def short_id(*parts: Any, length: int = 8) -> str:
    """Stable short id derived from several parts (run-id suffixes, failure ids)."""
    return stable_hash(list(parts), length=length)


def hash_config(config: Any, *, length: int = DEFAULT_HASH_LENGTH) -> str:
    """Hash a resolved configuration mapping or object canonically."""
    return stable_hash(config, length=length)


def hash_prompt(prompt: Any, *, length: int = DEFAULT_HASH_LENGTH) -> str:
    """Hash a prompt string or prompt-protocol mapping deterministically."""
    if isinstance(prompt, str):
        return hash_text(prompt, length=length)
    return stable_hash(prompt, length=length)


def hash_dataset(path: str | Path, *, length: int = DEFAULT_HASH_LENGTH) -> str:
    """Hash dataset bytes by path (streaming, platform-independent)."""
    return hash_file(path, length=length)


def hash_task(task: Any, *, length: int = DEFAULT_HASH_LENGTH) -> str:
    """Hash a task selection/episode definition canonically."""
    return stable_hash(task, length=length)


__all__ = [
    "DEFAULT_HASH_LENGTH", "canonical_json", "stable_hash", "hash_text", "hash_bytes",
    "hash_file", "short_id", "hash_config", "hash_prompt", "hash_dataset", "hash_task",
]
