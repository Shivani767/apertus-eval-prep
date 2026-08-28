from __future__ import annotations

from pathlib import Path

from transformers import AutoTokenizer

from apertus_eval_prep.config import RunConfig
from apertus_eval_prep.prompting import load_fewshot, load_prompt_spec, resolve_system, wrap_item
from apertus_eval_prep.prompts import load_items
from apertus_eval_prep.templates import render_prompt


def dump_prompts(cfg: RunConfig, repo_root: Path, n: int = 4) -> str:
    tokenizer = AutoTokenizer.from_pretrained(
        cfg.tokenizer_name(),
        revision=cfg.revision,
        trust_remote_code=True,
    )
    items = load_items(
        repo_root / cfg.data_path, cfg.tasks, cfg.limit, paraphrase_id=cfg.paraphrase_id
    )[:n]
    spec = load_prompt_spec(repo_root, cfg.prompt_id)
    fewshot_by_task = None
    if spec is not None and spec.fewshot and cfg.fewshot_path:
        fewshot_by_task = load_fewshot(repo_root / cfg.fewshot_path, cfg.tasks)
    system = resolve_system(cfg.system_prompt, spec)
    chunks = [
        f"model={cfg.model_id}",
        f"tokenizer={cfg.tokenizer_name()}",
        f"chat_template={cfg.chat_template}",
        f"thinking_mode={cfg.thinking_mode}",
        f"prompt_id={cfg.prompt_id!r}",
        f"system_prompt={system!r}",
        "",
        "Special tokens are visible. This is how you debug a train vs serve mismatch.",
        "=" * 72,
        "",
    ]
    for item in items:
        user_text = wrap_item(item, spec, fewshot_by_task)
        rendered = render_prompt(tokenizer, user_text, cfg.chat_template, system, thinking=cfg.thinking_mode)
        chunks.append(f"## {item.id}  task={item.task}  gold={item.gold}")
        chunks.append(rendered)
        chunks.append("")
        chunks.append("-" * 72)
        chunks.append("")
    return "\n".join(chunks)
