from __future__ import annotations

from pathlib import Path

from transformers import AutoTokenizer

from apertus_eval_prep.config import RunConfig
from apertus_eval_prep.prompts import load_items
from apertus_eval_prep.templates import render_prompt


def dump_prompts(cfg: RunConfig, repo_root: Path, n: int = 4) -> str:
    tokenizer = AutoTokenizer.from_pretrained(cfg.tokenizer_name(), revision=cfg.revision)
    items = load_items(repo_root / cfg.data_path, cfg.tasks, cfg.limit)[:n]
    chunks = [
        f"model={cfg.model_id}",
        f"tokenizer={cfg.tokenizer_name()}",
        f"chat_template={cfg.chat_template}",
        f"system_prompt={cfg.system_prompt!r}",
        "",
        "Special tokens are visible. This is how you debug a train vs serve mismatch.",
        "=" * 72,
        "",
    ]
    for item in items:
        rendered = render_prompt(tokenizer, item.prompt, cfg.chat_template, cfg.system_prompt)
        chunks.append(f"## {item.id}  task={item.task}  gold={item.gold}")
        chunks.append(rendered)
        chunks.append("")
        chunks.append("-" * 72)
        chunks.append("")
    return "\n".join(chunks)
