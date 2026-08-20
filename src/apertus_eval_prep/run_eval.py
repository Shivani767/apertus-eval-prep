from __future__ import annotations

from pathlib import Path
from typing import Any

from apertus_eval_prep.config import RunConfig
from apertus_eval_prep.manifest import build_manifest
from apertus_eval_prep.prompting import load_fewshot, load_prompt_spec, resolve_system, wrap_item
from apertus_eval_prep.prompts import load_items
from apertus_eval_prep.scoring import is_correct, predicted, summarize_latency, summarize_tasks
from apertus_eval_prep.templates import render_prompt


INCOMPARABILITY = [
    "Same frozen items, same gold extractor, still not comparable if any of these differ:",
    "chat_template, tokenizer id/revision, max_new_tokens, sampling (temperature/top_p/seed),",
    "prompt_id / few-shot, quantization, stop tokens, dtype, hardware, or backend.",
    "Generative exact-match is not lm-eval loglikelihood. Rankings need Wilson CIs.",
    "only compare two runs when the manifest.settings block matches except the one knob you changed.",
]


def _backend(cfg: RunConfig):
    if cfg.backend == "hf":
        from apertus_eval_prep.backends.hf import HFBackend

        return HFBackend(cfg)
    if cfg.backend == "vllm":
        from apertus_eval_prep.backends.vllm_backend import VLLMBackend

        return VLLMBackend(cfg)
    raise ValueError(cfg.backend)


def run_eval(cfg: RunConfig, repo_root: Path) -> dict[str, Any]:
    data_path = (repo_root / cfg.data_path).resolve()
    items = load_items(data_path, cfg.tasks, cfg.limit)
    if not items:
        raise SystemExit(f"No items loaded from {data_path} for tasks={cfg.tasks}")

    spec = load_prompt_spec(repo_root, cfg.prompt_id)
    fewshot_by_task = None
    if spec is not None and spec.fewshot:
        if not cfg.fewshot_path:
            raise SystemExit(f"prompt_id={cfg.prompt_id} needs fewshot_path")
        fewshot_by_task = load_fewshot(repo_root / cfg.fewshot_path, cfg.tasks)
    system = resolve_system(cfg.system_prompt, spec)

    backend = _backend(cfg)
    tokenizer = getattr(backend, "tokenizer", None)
    if tokenizer is None:
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(
            cfg.tokenizer_name(),
            revision=cfg.revision,
            trust_remote_code=True,
        )

    rows = []
    for i, item in enumerate(items, start=1):
        user_text = wrap_item(item, spec, fewshot_by_task)
        rendered = render_prompt(tokenizer, user_text, cfg.chat_template, system)
        gen = backend.generate_one(rendered, cfg.max_new_tokens)
        ok = is_correct(item.task, gen.text, item.gold)
        pred = predicted(item.task, gen.text)
        row = {
            "id": item.id,
            "task": item.task,
            "language": item.language,
            "gold": item.gold,
            "predicted": pred,
            "correct": ok,
            "generation": gen.text,
            "ttft_ms": round(gen.ttft_ms, 2) if gen.ttft_ms is not None else None,
            "e2e_ms": round(gen.e2e_ms, 2),
            "num_new_tokens": gen.num_new_tokens,
            "tokens_per_sec": round(gen.tokens_per_sec, 3) if gen.tokens_per_sec else None,
            "prompt_chars": len(rendered),
        }
        rows.append(row)
        print(
            f"[{i}/{len(items)}] {item.id} correct={ok} pred={pred!r} "
            f"ttft_ms={row['ttft_ms']}",
            flush=True,
        )

    settings = cfg.to_dict()
    settings["device"] = getattr(backend, "device", cfg.backend)
    payload = {
        "manifest": build_manifest(repo_root, settings),
        "incomparability": INCOMPARABILITY,
        "tasks": summarize_tasks(rows),
        "latency": summarize_latency(rows),
        "items": rows,
    }
    return payload
