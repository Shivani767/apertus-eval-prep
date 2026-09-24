"""JSON/YAML/JSONL I/O with strict, auditable behaviour.

Rules enforced here:
* JSON output is always valid JSON (non-finite floats become ``null``).
* Writes are atomic (temp file + ``os.replace``) so a crashed run cannot leave a
  half-written manifest.
* JSONL appends are line-buffered and never rewrite existing lines, which keeps
  per-example records append-only and auditable.
"""

from __future__ import annotations

import dataclasses
import enum
import json
import math
import os
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

JSONValue = Any


def _sanitize(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _sanitize(dataclasses.asdict(value))
    if isinstance(value, enum.Enum):
        return _sanitize(value.value)
    if isinstance(value, Mapping):
        return {str(k): _sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return [_sanitize(v) for v in sorted(value, key=str)]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def to_jsonable(value: Any) -> JSONValue:
    """Convert dataclasses/enums/paths/sets to strict-JSON-safe structures."""
    return _sanitize(value)


def atomic_write_text(path: str | Path, text: str, *, encoding: str = "utf-8") -> Path:
    """Write ``text`` atomically; returns the final path."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fh.write(text)
        os.replace(tmp_name, target)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    return target


def write_text(path: str | Path, text: str) -> Path:
    return atomic_write_text(path, text)


def read_text(path: str | Path, *, encoding: str = "utf-8") -> str:
    return Path(path).read_text(encoding=encoding)


def write_json(path: str | Path, payload: Any, *, indent: int = 2) -> Path:
    """Write strict JSON (``allow_nan=False`` after sanitising)."""
    text = json.dumps(to_jsonable(payload), indent=indent, ensure_ascii=False, allow_nan=False)
    return atomic_write_text(path, text + "\n")


def read_json(path: str | Path) -> JSONValue:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_yaml(path: str | Path, payload: Any) -> Path:
    text = yaml.safe_dump(to_jsonable(payload), sort_keys=False, allow_unicode=True)
    return atomic_write_text(path, text)


def read_yaml(path: str | Path) -> dict[str, Any]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ValueError(f"{path}: expected a YAML mapping at the top level")
    return dict(raw)


def append_jsonl(path: str | Path, records: Iterable[Any]) -> Path:
    """Append records as one compact JSON object per line (append-only)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        for record in records:
            line = json.dumps(to_jsonable(record), ensure_ascii=False, allow_nan=False)
            fh.write(line + "\n")
    return target


def read_jsonl(path: str | Path) -> list[JSONValue]:
    """Read a JSONL file; a missing file reads as an empty list."""
    target = Path(path)
    if not target.exists():
        return []
    rows: list[JSONValue] = []
    for lineno, line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:  # loud, never silently skipped
            raise ValueError(f"{target}:{lineno}: invalid JSON line: {exc}") from exc
    return rows


def write_jsonl(path: str | Path, records: Sequence[Any]) -> Path:
    """Overwrite a JSONL file (used for scored examples; raw outputs append)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(to_jsonable(r), ensure_ascii=False, allow_nan=False) for r in records
    ]
    return atomic_write_text(target, "".join(line + "\n" for line in lines))
