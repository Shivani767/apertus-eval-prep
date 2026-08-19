from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from apertus_eval_prep.compare import compare_runs, to_markdown
from apertus_eval_prep.config import load_config


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() and (parent / "data" / "eval_set.jsonl").exists():
            return parent
    return Path.cwd()


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", required=True, help="YAML config under configs/")
    p.add_argument("--backend", choices=["hf", "vllm"])
    p.add_argument("--chat-template", dest="chat_template", choices=["tokenizer", "none", "mismatched"])
    p.add_argument("--model-id", dest="model_id")
    p.add_argument("--limit", type=int)
    p.add_argument("--out", required=True, help="Output path")


def _overrides(args: argparse.Namespace) -> dict:
    return {
        "backend": args.backend,
        "chat_template": args.chat_template,
        "model_id": args.model_id,
        "limit": args.limit,
    }


def cmd_eval(args: argparse.Namespace) -> int:
    from apertus_eval_prep.run_eval import run_eval

    root = repo_root()
    cfg = load_config(args.config, _overrides(args))
    payload = run_eval(cfg, root)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tasks = payload["tasks"]
    print(f"\nWrote {out}")
    print(json.dumps({"tasks": tasks, "latency": payload["latency"]}, indent=2))
    return 0


def cmd_dump(args: argparse.Namespace) -> int:
    from apertus_eval_prep.dump_prompts import dump_prompts

    root = repo_root()
    cfg = load_config(args.config, _overrides(args))
    text = dump_prompts(cfg, root, n=args.n)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"Wrote {out}")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    report = compare_runs(Path(args.a), Path(args.b))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "md":
        out.write_text(to_markdown(report), encoding="utf-8")
    else:
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(out.read_text(encoding="utf-8"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apertus-eval-prep",
        description="Frozen-prompt eval harness: HF generate vs vLLM, chat-template ablations.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_eval = sub.add_parser("eval", help="Score the frozen slice and write JSON.")
    _add_common(p_eval)
    p_eval.set_defaults(func=cmd_eval)

    p_dump = sub.add_parser("dump-prompts", help="Write rendered prompts with special tokens visible.")
    _add_common(p_dump)
    p_dump.add_argument("--n", type=int, default=4)
    p_dump.set_defaults(func=cmd_dump)

    p_cmp = sub.add_parser("compare", help="Diff two eval JSON files.")
    p_cmp.add_argument("a")
    p_cmp.add_argument("b")
    p_cmp.add_argument("--out", required=True)
    p_cmp.add_argument("--format", choices=["md", "json"], default="md")
    p_cmp.set_defaults(func=cmd_compare)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
