"""Mid-run JSONL so a killed Colab cell can resume without re-scoring items."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any


def mirror_checkpoint(path: Path) -> None:
    dest_dir = os.environ.get("APERTUS_CHECKPOINT_DIR")
    if not dest_dir or not path.exists():
        return
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest / path.name)


def load_partial(path: Path, fingerprint: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        return []
    meta = json.loads(lines[0])
    if not meta.get("_checkpoint") or meta.get("fingerprint") != fingerprint:
        path.unlink()
        return []
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ln in lines[1:]:
        row = json.loads(ln)
        item_id = row.get("id")
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        rows.append(row)
    return rows


def start_partial(path: Path, fingerprint: str, n_expected: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {"_checkpoint": True, "fingerprint": fingerprint, "n_expected": n_expected}
    path.write_text(json.dumps(meta, ensure_ascii=False) + "\n", encoding="utf-8")
    mirror_checkpoint(path)


def append_partial(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    mirror_checkpoint(path)


def drop_partial(path: Path) -> None:
    if path.exists():
        path.unlink()
    dest_dir = os.environ.get("APERTUS_CHECKPOINT_DIR")
    if dest_dir:
        twin = Path(dest_dir) / path.name
        if twin.exists():
            twin.unlink()
