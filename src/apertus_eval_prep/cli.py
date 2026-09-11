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
    p.add_argument("--thinking-mode", dest="thinking_mode", action=argparse.BooleanOptionalAction)
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
        "thinking_mode",
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


def cmd_reproduce(args: argparse.Namespace) -> int:
    from apertus_eval_prep.reproduce import (
        find_registry_row,
        render_reproduction_markdown,
        render_verification_markdown,
        reproduction_plan,
        verify_reproduction,
    )

    root = repo_root()
    row = find_registry_row(
        Path(args.registry),
        config_hash=args.config_hash,
        run_id=args.run_id,
        experiment_id=args.experiment_id,
    )
    if row is None:
        print("No matching registry row.", file=sys.stderr)
        return 1
    plan = reproduction_plan(row, root)
    text = render_reproduction_markdown(plan)
    if args.check:
        ver = verify_reproduction(row, root)
        text += "\n\n---\n\n" + render_verification_markdown(ver)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"Wrote {out}")
    print(text)
    return 0


def cmd_benchmark_report(args: argparse.Namespace) -> int:
    from apertus_eval_prep.benchmark_report import write_benchmark_report

    md_path = write_benchmark_report(args.run, Path(args.out))
    print(f"Wrote {md_path}")
    print(f"Wrote {md_path.with_suffix('.json')}")
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


def cmd_ers(args: argparse.Namespace) -> int:
    """Evaluation Reliability Score (DERIVED) from a committed registry.

    Builds the models x configs accuracy matrix from registry rows sharing a
    task+n. Models with < 2 measured cells are listed as excluded (they have
    no within-model protocol spread). Missing cells stay None — never zero.
    """
    import json as _json

    from apertus_eval_prep.reliability import evaluation_reliability_score
    from apertus_eval_prep.registry import load_registry

    root = repo_root()
    rows = load_registry(Path(args.registry))
    # NOTE: registry rows carry only the cross-task aggregate (overall);
    # per-task matrices need the run blobs and are out of scope here.
    cells: dict[str, dict[str, float]] = {}
    n_per_cell: int | None = None
    for r in rows:
        if r.get("status") != "ok" or not r.get("overall"):
            continue
        n = int(r["overall"].get("n", 0) or 0)
        if n_per_cell is None:
            n_per_cell = n
        elif n != n_per_cell:
            print(f"warning: mixed n ({n_per_cell} vs {n}); using first, "
                  f"skip? run={r.get('run_id')}")
        cells.setdefault(r["model_id"], {})[
            f"{r['factor']}={r['factor_level']}"
        ] = float(r["overall"]["accuracy"])

    configs = sorted({c for m in cells.values() for c in m})
    matrix, names = [], []
    for model, cfgs in cells.items():
        if len(cfgs) < 2:
            continue
        names.append(model)
        matrix.append([cfgs.get(c) for c in configs])
    reports = {}
    if len(names) >= 2 and n_per_cell:
        out = evaluation_reliability_score(
            matrix, n_per_cell=n_per_cell, n_boot=args.n_boot, seed=args.seed
        )
        out["n_per_cell"] = n_per_cell
        out["models"] = names
        out["n_configs_used"] = len(configs)
        out["n_missing_cells"] = sum(1 for row in matrix for v in row if v is None)
        out["excluded_models_lt2_cells"] = sorted(set(cells) - set(names))
        out["registry"] = str(args.registry)
        out["provenance"] = "DERIVED from measured registry rows; not a new measurement"
        reports["all_cells"] = out

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ers.json"
    out_path.write_text(_json.dumps(reports, indent=2) + "\n", encoding="utf-8")

    md = ["# Evaluation Reliability Score (provisional, DERIVED)",
          "",
          "Source registry: `" + str(args.registry) + "`. "
          "Components that need inputs the registry lacks are excluded and listed.",
          ""]
    for name, r in reports.items():
        md.append(f"## {name}")
        md.append("")
        md.append(f"- **ERS: {r['ers']}** ({r['n_components']} components, provisional weights)")
        comps = ", ".join(
            f"{k}={v:.3f}" if v is not None else f"{k}=None"
            for k, v in r["components"].items()
        )
        md.append(f"- components: {comps}")
        if r["excluded_models_lt2_cells"]:
            md.append(f"- excluded (<2 cells): {', '.join(r['excluded_models_lt2_cells'])}")
        md.append(f"- bootstrap: tau={r['bootstrap']['mean_tau']}, "
                  f"p(reversal)={r['bootstrap']['p_any_reversal']} "
                  f"over {r['n_configs_used']} configs")
        md.append("")
    (out_dir / "ers.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Wrote {out_path} and ers.md ({len(reports)} task groups)")
    return 0


def cmd_pareto(args: argparse.Namespace) -> int:
    """Pareto frontier (quality vs cost) across scored run files.

    Cost from the recorded latency block (DERIVED est_total_s), quality from
    per-item correctness. Points missing either coordinate are excluded from
    the frontier and listed — never placed at zero.
    """
    import json as _json

    from apertus_eval_prep.cost import extract_cost
    from apertus_eval_prep.pareto import pareto_front, render_pareto_markdown

    points = []
    for spec in args.run:
        if "=" in spec:
            path, label = spec.split("=", 1)
        else:
            path, label = spec, Path(spec).stem
        with open(path, encoding="utf-8") as f:
            blob = _json.load(f)
        rec = extract_cost(blob, run_id=label)
        items = blob.get("items") or []
        correct = [1 if it.get("correct") else 0 for it in items]
        acc = sum(correct) / len(correct) if correct else None
        points.append({
            "label": label,
            "cost_est_total_s": rec.est_total_s,
            "n_calls": rec.n_calls,
            "tokens_per_sec_mean": rec.tokens_per_sec_mean,
            "quality_accuracy": acc,
            "n_items": len(correct),
        })

    analysis = pareto_front(
        points, x_key="cost_est_total_s", y_key="quality_accuracy"
    )
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "pareto.json").write_text(
        _json.dumps(analysis, indent=2) + "\n", encoding="utf-8"
    )
    md_path = out_dir / "pareto.md"
    md = render_pareto_markdown(
        {
            "frontier": [
                {**p, "cost": p["cost_est_total_s"], "acc": p["quality_accuracy"]}
                for p in analysis["frontier"]
            ],
            "dominated": [
                {**p, "cost": p["cost_est_total_s"], "acc": p["quality_accuracy"]}
                for p in analysis["dominated"]
            ],
            "excluded": [
                {**p, "cost": p["cost_est_total_s"], "acc": p["quality_accuracy"]}
                for p in analysis["excluded"]
            ],
            "x_key": "cost",
            "y_key": "acc",
        }
    )
    md_path.write_text(md, encoding="utf-8")
    print(f"Wrote {out_dir / 'pareto.json'} and {md_path}")
    return 0


def cmd_failures(args: argparse.Namespace) -> int:
    """Failure taxonomy report across scored run files (measured counts)."""
    import json as _json

    from apertus_eval_prep.failures import (
        failure_taxonomy,
        render_failure_markdown,
    )

    reports = {}
    for spec in args.run:
        if "=" in spec:
            path, label = spec.split("=", 1)
        else:
            path, label = spec, Path(spec).stem
        with open(path, encoding="utf-8") as f:
            blob = _json.load(f)
        reports[label] = failure_taxonomy(blob)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "failures.json").write_text(
        _json.dumps(reports, indent=2) + "\n", encoding="utf-8"
    )
    md_path = out_dir / "failures.md"
    md_path.write_text(render_failure_markdown(reports), encoding="utf-8")
    print(f"Wrote {out_dir / 'failures.json'} and {md_path}")
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    """Aggregate research report: coverage, ERS, deviation checks, failures."""
    import json as _json

    from apertus_eval_prep.dashboard import build_dashboard, render_dashboard_markdown

    root = repo_root()
    failure_runs = [Path(p) for p in (args.run or [])]
    d = build_dashboard(
        Path(args.registry), root,
        failure_runs=failure_runs or None,
        n_boot=args.n_boot, seed=args.seed,
    )
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "dashboard.json").write_text(
        _json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    md_path = out_dir / "dashboard.md"
    md_path.write_text(render_dashboard_markdown(d), encoding="utf-8")
    print(f"Wrote {out_dir / 'dashboard.json'} and {md_path}")
    return 0


def cmd_profile(args: argparse.Namespace) -> int:
    """Runtime/tokenizer profile of a scored run (derived from measured items)."""
    import json as _json

    from apertus_eval_prep.profile import render_profile_markdown, runtime_profile

    with open(args.run, encoding="utf-8") as f:
        blob = _json.load(f)
    prof = runtime_profile(blob)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.run).stem
    (out_dir / f"profile_{stem}.json").write_text(
        _json.dumps(prof, indent=2) + "\n", encoding="utf-8"
    )
    md_path = out_dir / f"profile_{stem}.md"
    md_path.write_text(render_profile_markdown(prof), encoding="utf-8")
    print(f"Wrote {out_dir / f'profile_{stem}.json'} and {md_path}")
    return 0


def cmd_catalog(args: argparse.Namespace) -> int:
    """Regenerate the fingerprinted dataset/model catalog (MEASURED+DERIVED)."""
    import json as _json

    from apertus_eval_prep.catalog import build_catalog, render_catalog_markdown

    root = repo_root()
    cat = build_catalog(root, Path(args.registry) if args.registry else root / "results/registry_paper.jsonl")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "catalog.json").write_text(_json.dumps(cat, indent=2) + "\n", encoding="utf-8")
    md = out / "catalog.md"
    md.write_text(render_catalog_markdown(cat), encoding="utf-8")
    print(f"Wrote {out / 'catalog.json'} and {md}")
    return 0


def cmd_experiment(args: argparse.Namespace) -> int:
    """Run a full experiment end-to-end (config → sweep → stats → report)."""
    from apertus_eval_prep.experiment_runner import run_experiment

    root = repo_root()
    config_path = Path(args.config).resolve()
    registry_path = Path(args.registry).resolve() if args.registry else root / "results/registry_paper.jsonl"
    output_dir = Path(args.out).resolve()

    run = run_experiment(
        args.id,
        config_path,
        root,
        registry_path=registry_path,
        output_dir=output_dir,
        n_boot=args.n_boot,
        seed=args.seed,
    )
    print(f"Wrote {output_dir / (args.id + '_result.json')}")
    print(f"Wrote {output_dir / (args.id + '_report.md')}")
    print(f"Cells measured: {len(run.results)}")
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
        help="Run OFAT cells for this factor only (control, prompt_id, seed, backend, quantization, sampled, paraphrase_id, thinking_mode).",
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

    p_bench = sub.add_parser(
        "benchmark-report",
        help="Multi-model benchmark report: thinking, quant, safety, cost, multilingual.",
    )
    p_bench.add_argument(
        "--run",
        action="append",
        required=True,
        help="path or path=label. Repeat for each scored JSON.",
    )
    p_bench.add_argument("--out", default="reports/benchmark")
    p_bench.set_defaults(func=cmd_benchmark_report)

    p_repro = sub.add_parser("reproduce", help="Print replay command from registry row.")
    p_repro.add_argument("--registry", default="results/registry_paper.jsonl")
    p_repro.add_argument("--run-id", dest="run_id")
    p_repro.add_argument("--config-hash", dest="config_hash")
    p_repro.add_argument("--experiment-id", dest="experiment_id")
    p_repro.add_argument("--out", help="Optional markdown output path")
    p_repro.add_argument(
        "--check",
        action="store_true",
        help="Cross-check the artifact against the registry and report deviations.",
    )
    p_repro.set_defaults(func=cmd_reproduce)

    p_ers = sub.add_parser(
        "ers",
        help="Evaluation Reliability Score (DERIVED) from a committed registry.",
    )
    p_ers.add_argument("--registry", default="results/registry_paper.jsonl")
    p_ers.add_argument("--out", default="reports/ers")
    p_ers.add_argument("--task", help="Restrict to one task id (default: all).")
    p_ers.add_argument("--n-boot", dest="n_boot", type=int, default=300)
    p_ers.add_argument("--seed", type=int, default=0)
    p_ers.set_defaults(func=cmd_ers)

    p_pareto = sub.add_parser(
        "pareto",
        help="Pareto frontier (accuracy vs cost) across scored run files.",
    )
    p_pareto.add_argument(
        "--run",
        action="append",
        required=True,
        help="path or path=label. Repeat for each scored JSON.",
    )
    p_pareto.add_argument("--out", default="reports/pareto")
    p_pareto.set_defaults(func=cmd_pareto)

    p_fail = sub.add_parser(
        "failures",
        help="Failure taxonomy (runtime/empty/unparseable/wrong) over scored runs.",
    )
    p_fail.add_argument(
        "--run",
        action="append",
        required=True,
        help="path or path=label. Repeat for each scored JSON.",
    )
    p_fail.add_argument("--out", default="reports/failures")
    p_fail.set_defaults(func=cmd_failures)

    p_dash = sub.add_parser(
        "dashboard",
        help="Aggregate research report: coverage, ERS, deviations, failures.",
    )
    p_dash.add_argument("--registry", default="results/registry_paper.jsonl")
    p_dash.add_argument("--out", default="reports/dashboard")
    p_dash.add_argument("--n-boot", dest="n_boot", type=int, default=300)
    p_dash.add_argument("--seed", type=int, default=0)
    p_dash.add_argument(
        "--run",
        action="append",
        help="Optional scored-run JSON for the failure-taxonomy section (repeatable).",
    )
    p_dash.set_defaults(func=cmd_dashboard)

    p_prof = sub.add_parser(
        "profile",
        help="Runtime/tok-s profile by task and language from a scored run.",
    )
    p_prof.add_argument("--run", required=True, help="Scored run JSON.")
    p_prof.add_argument("--out", default="reports/profile")
    p_prof.set_defaults(func=cmd_profile)

    p_cat = sub.add_parser(
        "catalog",
        help="Fingerprint datasets (sha256) and model coverage from the registry.",
    )
    p_cat.add_argument(
        "--registry", default=None,
        help="Registry JSONL for model coverage (default: results/registry_paper.jsonl).",
    )
    p_cat.add_argument("--out", default="data/catalog")
    p_cat.set_defaults(func=cmd_catalog)

    p_exp = sub.add_parser(
        "experiment",
        help="Run a full experiment end-to-end (config → sweep → stats → report).",
    )
    p_exp.add_argument("--config", required=True, help="Experiment config YAML.")
    p_exp.add_argument("--id", required=True, help="Experiment ID (used for output filenames).")
    p_exp.add_argument("--registry", default=None, help="Registry JSONL (default: results/registry_paper.jsonl).")
    p_exp.add_argument("--out", default="reports/experiments", help="Output directory.")
    p_exp.add_argument("--n-boot", dest="n_boot", type=int, default=300)
    p_exp.add_argument("--seed", type=int, default=0)
    p_exp.set_defaults(func=cmd_experiment)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
