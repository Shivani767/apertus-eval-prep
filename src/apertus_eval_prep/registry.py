from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


HASH_KEYS = (
    "model_id",
    "tokenizer_id",
    "revision",
    "backend",
    "chat_template",
    "max_new_tokens",
    "seed",
    "dtype",
    "quantization",
    "temperature",
    "top_p",
    "prompt_id",
    "data_path",
    "tasks",
    "limit",
    "fewshot_path",
)


def config_hash(settings: dict[str, Any]) -> str:
    payload = {k: settings.get(k) for k in HASH_KEYS}
    # Omit default paraphrase so existing paper-matrix hashes stay stable.
    para = settings.get("paraphrase_id")
    if para not in (None, "", "orig"):
        payload["paraphrase_id"] = para
    if settings.get("thinking_mode"):
        payload["thinking_mode"] = True
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def load_registry(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def completed_hashes(rows: Iterable[dict[str, Any]]) -> set[str]:
    return {r["config_hash"] for r in rows if r.get("status") == "ok" and r.get("config_hash")}


def append_registry(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = dict(row)
    row.setdefault("utc", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
