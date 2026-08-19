from __future__ import annotations

from pathlib import Path
from typing import Any

from apertus_eval_prep.config import RunConfig
from apertus_eval_prep.manifest import build_manifest
from apertus_eval_prep.prompts import load_items
from apertus_eval_prep.scoring import is_correct, predicted, summarize_latency, summarize_tasks
from apertus_eval_prep.templates import render_prompt


INCOMPARABILITY = [
    "Same frozen items, same gold extractor, still not comparable if any of these differ:",
    "chat_template (tokenizer vs none vs mismatched), tokenizer id/revision, max_new_tokens,",
    "sampling (this harness is greedy only), stop tokens, dtype, hardware, or backend.",
    "swiss-ai/evals-post-train notes generation scores can move between HF and vLLM;",
    "only compare two runs when the manifest.settings block matches except the one knob you changed.",
]


def _backend(cfg: RunConfig):
    tok = cfg.tokenizer_name()
    if cfg.backend == "hf":
        from apertus_eval_prep.backends.hf import HFBackend

        return HFBackend(cfg.model_id, tok, cfg.revision, cfg.dtype, cfg.seed)
    if cfg.backend == "vllm":
        from apertus_eval_prep.backends.vllm_backend import VLLMBackend

        return VLLMBackend(cfg.model_id, tok, cfg.revision, cfg.dtype, cfg.seed)
    raise ValueError(cfg.backend)


def run_eval(cfg: RunConfig, repo_root: Path) -> dict[str, Any]:
    data_path = (repo_root / cfg.data_path).resolve()
    items = load_items(data_path, cfg.tasks, cfg.limit)
    if not items:
        raise SystemExit(f"No items loaded from {data_path} for tasks={cfg.tasks}")

    backend = _backend(cfg)
    tokenizer = getattr(backend, "tokenizer", None)
    if tokenizer is None:
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(cfg.tokenizer_name(), revision=cfg.revision)

    rows = []
    for i, item in enumerate(items, start=1):
        rendered = render_prompt(tokenizer, item.prompt, cfg.chat_template, cfg.system_prompt)
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
