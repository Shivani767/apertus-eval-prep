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
    p.add_argument("--quantization", choices=["none", "int8", "int4"])
    p.add_argument("--temperature", type=float)
    p.add_argument("--prompt-id", dest="prompt_id")
    p.add_argument("--seed", type=int)
    p.add_argument("--out", required=True, help="Output path")


def _overrides(args: argparse.Namespace) -> dict:
    keys = (
        "backend",
        "chat_template",
        "model_id",
        "limit",
        "quantization",
        "temperature",
        "prompt_id",
        "seed",
    )
    return {k: getattr(args, k, None) for k in keys}


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


def cmd_sweep(args: argparse.Namespace) -> int:
    from apertus_eval_prep.sweep import execute_sweep

    root = repo_root()
    planned = execute_sweep(
        study_path=Path(args.config),
        repo_root=root,
        out_dir=Path(args.out_dir),
        registry_path=Path(args.registry),
        profile=args.profile,
        limit=args.limit,
        dry_run=args.dry_run,
        force=args.force,
        only_model=args.only_model,
        only_factor=args.only_factor,
    )
    print(json.dumps({"n_cells": len(planned), "n_skip": sum(1 for p in planned if p["skipped"])}, indent=2))
    if args.dry_run:
        print(json.dumps(planned, indent=2))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from apertus_eval_prep.registry import load_registry
    from apertus_eval_prep.report import (
        collect_runs,
        ranking_table,
        render_markdown_report,
        write_plots,
    )

    root = repo_root()
    rows = load_registry(Path(args.registry))
    blobs = collect_runs(rows, root)
    analysis = ranking_table(blobs)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    md_path = out / "stability.md"
    md_path.write_text(render_markdown_report(analysis), encoding="utf-8")
    (out / "analysis.json").write_text(json.dumps(analysis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    plots = write_plots(analysis, out)
    print(f"Wrote {md_path}")
    for p in plots:
        print(p)
    return 0


def cmd_paper_tables(args: argparse.Namespace) -> int:
    from apertus_eval_prep.registry import load_registry
    from apertus_eval_prep.report import collect_runs, paper_tables, ranking_table

    root = repo_root()
    rows = load_registry(Path(args.registry))
    analysis = ranking_table(collect_runs(rows, root))
    text = paper_tables(analysis)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"Wrote {out}")
    return 0


def cmd_paper(args: argparse.Namespace) -> int:
    from apertus_eval_prep.registry import load_registry
    from apertus_eval_prep.report import collect_runs, paper_tables, ranking_table, render_stability_paper

    root = repo_root()
    rows = load_registry(Path(args.registry))
    blobs = collect_runs(rows, root)
    analysis = ranking_table(blobs)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tables_path = out_dir / "_generated_tables.md"
    tables_path.write_text(paper_tables(analysis), encoding="utf-8")
    n_ok = sum(1 for r in rows if r.get("status") == "ok")
    paper_path = out_dir / "stability.md"
    paper_path.write_text(
        render_stability_paper(analysis, blobs, n_t4_planned=34, n_registry_ok=n_ok),
        encoding="utf-8",
    )
    print(f"Wrote {tables_path}")
    print(f"Wrote {paper_path}")
    return 0


def cmd_ci_width(args: argparse.Namespace) -> int:
    from apertus_eval_prep.report import (
        ci_width_report,
        render_ci_width_markdown,
        write_ci_width_plot,
    )

    analysis = ci_width_report(args.run)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    md_path = out / "ci_width.md"
    md_path.write_text(render_ci_width_markdown(analysis), encoding="utf-8")
    plots = write_ci_width_plot(analysis, out)
    print(f"Wrote {md_path}")
    for p in plots:
        print(p)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apertus-eval-prep",
        description="Frozen-prompt eval harness: HF vs vLLM, ranking stability sweeps.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_eval = sub.add_parser("eval", help="Score a frozen slice and write JSON.")
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

    p_sweep = sub.add_parser("sweep", help="Expand OFAT cells and run (resumes via registry).")
    p_sweep.add_argument("--config", required=True)
    p_sweep.add_argument("--out-dir", default="results/runs")
    p_sweep.add_argument("--registry", default="results/registry.jsonl")
    p_sweep.add_argument("--profile", choices=["t4", "a10", "cpu"])
    p_sweep.add_argument("--limit", type=int, help="Cap items per task (Colab demo).")
    p_sweep.add_argument("--dry-run", action="store_true")
    p_sweep.add_argument("--force", action="store_true", help="Re-run cells already in the registry.")
    p_sweep.add_argument("--only-model", dest="only_model", help="Run OFAT cells for this model_id only.")
    p_sweep.add_argument(
        "--only-factor",
        dest="only_factor",
        help="Run OFAT cells for this factor only (control, prompt_id, seed, backend, quantization, sampled, paraphrase_id).",
    )
    p_sweep.set_defaults(func=cmd_sweep)

    p_report = sub.add_parser("report", help="Wilson CIs, Kendall tau, plots from the registry.")
    p_report.add_argument("--registry", default="results/registry.jsonl")
    p_report.add_argument("--out", default="reports/stability")
    p_report.set_defaults(func=cmd_report)

    p_paper_tables = sub.add_parser("paper-tables", help="Write markdown tables only (used by paper/).")
    p_paper_tables.add_argument("--registry", default="results/registry_paper.jsonl")
    p_paper_tables.add_argument("--out", default="paper/_generated_tables.md")
    p_paper_tables.set_defaults(func=cmd_paper_tables)

    p_paper = sub.add_parser("paper", help="Regenerate paper/stability.md and tables from registry_paper.jsonl.")
    p_paper.add_argument("--registry", default="results/registry_paper.jsonl")
    p_paper.add_argument("--out-dir", default="paper")
    p_paper.set_defaults(func=cmd_paper)

    p_ci = sub.add_parser("ci-width", help="Wilson CI width vs n from scored run JSON (not the paper matrix).")
    p_ci.add_argument(
        "--run",
        action="append",
        required=True,
        help="path or path=label. Repeat. Uses items already in the JSON.",
    )
    p_ci.add_argument("--out", default="reports/ci_width")
    p_ci.set_defaults(func=cmd_ci_width)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
