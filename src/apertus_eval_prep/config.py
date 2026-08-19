from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


VALID_BACKENDS = ("hf", "vllm")
VALID_TEMPLATES = ("tokenizer", "none", "mismatched")


@dataclass
class RunConfig:
    model_id: str
    tokenizer_id: str | None
    revision: str | None
    backend: str
    chat_template: str
    system_prompt: str | None
    max_new_tokens: int
    seed: int
    dtype: str
    data_path: str
    tasks: list[str]
    limit: int | None
    batch_size: int

    def tokenizer_name(self) -> str:
        return self.tokenizer_id or self.model_id

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_config(path: str | Path, overrides: dict[str, Any] | None = None) -> RunConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if overrides:
        for key, value in overrides.items():
            if value is not None:
                raw[key] = value
    cfg = RunConfig(
        model_id=raw["model_id"],
        tokenizer_id=raw.get("tokenizer_id"),
        revision=raw.get("revision"),
        backend=str(raw.get("backend", "hf")),
        chat_template=str(raw.get("chat_template", "tokenizer")),
        system_prompt=raw.get("system_prompt"),
        max_new_tokens=int(raw.get("max_new_tokens", 96)),
        seed=int(raw.get("seed", 0)),
        dtype=str(raw.get("dtype", "auto")),
        data_path=str(raw.get("data_path", "data/eval_set.jsonl")),
        tasks=list(raw.get("tasks") or []),
        limit=raw.get("limit"),
        batch_size=int(raw.get("batch_size", 1)),
    )
    if cfg.backend not in VALID_BACKENDS:
        raise ValueError(f"backend must be one of {VALID_BACKENDS}, got {cfg.backend}")
    if cfg.chat_template not in VALID_TEMPLATES:
        raise ValueError(f"chat_template must be one of {VALID_TEMPLATES}, got {cfg.chat_template}")
    if cfg.limit is not None:
        cfg.limit = int(cfg.limit)
    return cfg
