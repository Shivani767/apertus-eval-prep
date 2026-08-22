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
    paraphrase_id: str = "orig"
    paraphrase_group: str | None = None


def load_items(
    path: str | Path,
    tasks: list[str],
    limit: int | None,
    paraphrase_id: str | None = None,
) -> list[EvalItem]:
    wanted = set(tasks)
    per_task: dict[str, int] = {t: 0 for t in tasks}
    items: list[EvalItem] = []
    wanted_para = paraphrase_id if paraphrase_id not in (None, "") else None
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            task = raw["task"]
            if task not in wanted:
                continue
            item_para = str(raw.get("paraphrase_id") or "orig")
            if wanted_para is not None and item_para != wanted_para:
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
                    paraphrase_id=item_para,
                    paraphrase_group=raw.get("paraphrase_group"),
                )
            )
            per_task[task] += 1
    return items
