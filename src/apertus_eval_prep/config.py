from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


VALID_BACKENDS = ("hf", "vllm")
VALID_TEMPLATES = ("tokenizer", "none", "mismatched")
VALID_QUANTIZATION = ("none", "int8", "int4")


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
    quantization: str
    temperature: float
    top_p: float
    prompt_id: str | None
    fewshot_path: str | None
    experiment_id: str | None
    run_id: str | None
    paraphrase_id: str | None = None
    thinking_mode: bool = False
    cost_per_1m_input_tokens: float | None = None
    cost_per_1m_output_tokens: float | None = None

    def tokenizer_name(self) -> str:
        return self.tokenizer_id or self.model_id

    def do_sample(self) -> bool:
        return self.temperature > 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def comparable_settings(self) -> dict[str, Any]:
        """Knobs that make two scores incomparable if they differ."""
        return {
            "model_id": self.model_id,
            "tokenizer_id": self.tokenizer_id,
            "revision": self.revision,
            "backend": self.backend,
            "chat_template": self.chat_template,
            "max_new_tokens": self.max_new_tokens,
            "seed": self.seed,
            "dtype": self.dtype,
            "quantization": self.quantization,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "prompt_id": self.prompt_id,
            "paraphrase_id": self.paraphrase_id,
            "thinking_mode": self.thinking_mode,
            "data_path": self.data_path,
            "tasks": list(self.tasks),
            "limit": self.limit,
            "fewshot_path": self.fewshot_path,
        }


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
        quantization=str(raw.get("quantization", "none")),
        temperature=float(raw.get("temperature", 0.0)),
        top_p=float(raw.get("top_p", 1.0)),
        prompt_id=raw.get("prompt_id"),
        fewshot_path=raw.get("fewshot_path"),
        experiment_id=raw.get("experiment_id"),
        run_id=raw.get("run_id"),
        paraphrase_id=raw.get("paraphrase_id"),
        thinking_mode=bool(raw.get("thinking_mode", False)),
        cost_per_1m_input_tokens=raw.get("cost_per_1m_input_tokens"),
        cost_per_1m_output_tokens=raw.get("cost_per_1m_output_tokens"),
    )
    if cfg.cost_per_1m_input_tokens is not None:
        cfg.cost_per_1m_input_tokens = float(cfg.cost_per_1m_input_tokens)
    if cfg.cost_per_1m_output_tokens is not None:
        cfg.cost_per_1m_output_tokens = float(cfg.cost_per_1m_output_tokens)
    if cfg.backend not in VALID_BACKENDS:
        raise ValueError(f"backend must be one of {VALID_BACKENDS}, got {cfg.backend}")
    if cfg.chat_template not in VALID_TEMPLATES:
        raise ValueError(f"chat_template must be one of {VALID_TEMPLATES}, got {cfg.chat_template}")
    if cfg.quantization not in VALID_QUANTIZATION:
        raise ValueError(f"quantization must be one of {VALID_QUANTIZATION}, got {cfg.quantization}")
    if cfg.temperature < 0:
        raise ValueError("temperature must be >= 0")
    if cfg.limit is not None:
        cfg.limit = int(cfg.limit)
    return cfg
