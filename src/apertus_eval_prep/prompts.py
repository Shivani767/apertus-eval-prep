from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EvalItem:
    id: str
    task: str
    language: str
    gold: str
    prompt: str


def load_items(path: str | Path, tasks: list[str], limit: int | None) -> list[EvalItem]:
    wanted = set(tasks)
    per_task: dict[str, int] = {t: 0 for t in tasks}
    items: list[EvalItem] = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            task = raw["task"]
            if task not in wanted:
                continue
            if limit is not None and per_task[task] >= limit:
                continue
            items.append(
                EvalItem(
                    id=raw["id"],
                    task=task,
                    language=raw.get("language", "en"),
                    gold=str(raw["gold"]),
                    prompt=raw["prompt"],
                )
            )
            per_task[task] += 1
    return items
