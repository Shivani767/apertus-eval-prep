from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from apertus_eval_prep.prompts import EvalItem, load_items
from apertus_eval_prep.scoring import MATH_TASKS, MC_TASKS


@dataclass
class PromptSpec:
    id: str
    system: str | None
    fewshot: int
    instruction_mc: str
    instruction_math: str


def prompt_yaml_path(repo_root: Path, prompt_id: str) -> Path:
    return repo_root / "configs" / "prompts" / f"{prompt_id}.yaml"


def load_prompt_spec(repo_root: Path, prompt_id: str | None) -> PromptSpec | None:
    """None means the frozen item.prompt is already the full user string."""
    if not prompt_id:
        return None
    path = prompt_yaml_path(repo_root, prompt_id)
    if not path.exists():
        raise FileNotFoundError(f"prompt yaml not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return PromptSpec(
        id=str(raw.get("id", prompt_id)),
        system=raw.get("system"),
        fewshot=int(raw.get("fewshot", 0)),
        instruction_mc=str(raw.get("instruction_mc", "Reply with the letter only.")),
        instruction_math=str(
            raw.get("instruction_math", "Reason step by step. Put the final numeric answer on the last line.")
        ),
    )


def load_fewshot(path: str | Path, tasks: Iterable[str]) -> dict[str, list[EvalItem]]:
    items = load_items(path, list(tasks), limit=None)
    by_task: dict[str, list[EvalItem]] = {}
    for item in items:
        by_task.setdefault(item.task, []).append(item)
    return by_task


def _instruction(item: EvalItem, spec: PromptSpec) -> str:
    if item.task in MC_TASKS:
        return spec.instruction_mc
    if item.task in MATH_TASKS:
        return spec.instruction_math
    return spec.instruction_mc


def wrap_item(
    item: EvalItem,
    spec: PromptSpec | None,
    fewshot_by_task: dict[str, list[EvalItem]] | None = None,
) -> str:
    """Turn a frozen stem into the user message for this prompt variant.

    Official slices store question+choices only. The 28-item canary already
    includes instructions; those runs leave prompt_id unset and skip wrapping.
    """
    if spec is None:
        return item.prompt

    shots: list[EvalItem] = []
    if spec.fewshot and fewshot_by_task:
        pool = fewshot_by_task.get(item.task) or []
        shots = pool[: spec.fewshot]

    blocks: list[str] = []
    for shot in shots:
        blocks.append(f"{shot.prompt}\nAnswer: {shot.gold}")
    instr = _instruction(item, spec)
    blocks.append(f"{item.prompt}\n{instr}")
    return "\n\n".join(blocks)


def resolve_system(cfg_system: str | None, spec: PromptSpec | None) -> str | None:
    if spec is not None and spec.system:
        return spec.system
    return cfg_system
