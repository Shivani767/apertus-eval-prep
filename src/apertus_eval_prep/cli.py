from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from apertus_eval_prep.compare import compare_runs, to_markdown
from apertus_eval_prep.config import load_config
from apertus_eval_prep.core.evidence import EVIDENCE_MODES


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


def _registry_score_matrix(rows) -> dict:
    """Build the models x configs accuracy matrix from committed registry rows.

    Shared by ``ers`` and ``heldout`` so both analyses see identical cell
    semantics: only ``status == "ok"`` rows carrying a non-empty aggregate
    contribute; a model needs at least two measured cells to have any
    within-model protocol spread; and a missing (model, config) cell stays
    ``None`` — never zero, so an unmeasured cell cannot masquerade as a
    failing one.
    """
    cells: dict[str, dict[str, float]] = {}
    n_per_cell: int | None = None
    mixed_n: list[dict] = []
    for r in rows:
        if r.get("status") != "ok" or not r.get("overall"):
            continue
        n = int(r["overall"].get("n", 0) or 0)
        if n_per_cell is None:
            n_per_cell = n
        elif n != n_per_cell:
            mixed_n.append({"run_id": r.get("run_id"), "n": n, "expected": n_per_cell})
        cells.setdefault(r["model_id"], {})[
            f"{r['factor']}={r['factor_level']}"
        ] = float(r["overall"]["accuracy"])
    configs = sorted({c for m in cells.values() for c in m})
    matrix: list[list[float | None]] = []
    names: list[str] = []
    for model, cfgs in cells.items():
        if len(cfgs) < 2:
            continue
        names.append(model)
        matrix.append([cfgs.get(c) for c in configs])
    return {
        "matrix": matrix,
        "models": names,
        "configs": configs,
        "n_per_cell": n_per_cell,
        "excluded_models_lt2_cells": sorted(set(cells) - set(names)),
        "n_missing_cells": sum(1 for row in matrix for v in row if v is None),
        "mixed_n_warnings": mixed_n,
    }


def cmd_heldout(args: argparse.Namespace) -> int:
    """Held-out configuration generalization from a committed registry.

    Answers the budget question: given a matrix where ``b`` configurations have
    been run, how well can we predict the score and the ranking of the
    configurations we have NOT run?

    The estimator is fit on train configurations ONLY; held-out configurations
    are used for evaluation and never for fitting, so the curve is leakage-free
    by construction. Nothing here is a new measurement: every number is DERIVED
    from already-committed registry rows, and missing cells stay None.

    A "configuration" here is one ``(factor, factor_level)`` grid point, which is
    the grouping the paper's "31 committed configurations" cell count decomposes
    into. ``scripts/analyze_research_results.py`` instead keys on the compound
    four-factor identity, giving a different (also correct) configuration space;
    the two are not interchangeable, so results from them should not be mixed.
    """
    import json as _json

    from apertus_eval_prep.heldout import rank_instability_report, run_heldout_experiments
    from apertus_eval_prep.registry import load_registry

    rows = load_registry(Path(args.registry))
    built = _registry_score_matrix(rows)
    matrix, names, configs = built["matrix"], built["models"], built["configs"]
    n_c = len(configs)

    for w in built["mixed_n_warnings"]:
        print(f"warning: mixed n (expected {w['expected']}, got {w['n']}); "
              f"comparability not guaranteed; run={w['run_id']}")
    if len(names) < 2:
        print("error: need at least 2 models with >= 2 measured cells; "
              f"found {len(names)} from {args.registry}", file=sys.stderr)
        return 1
    if n_c < 3:
        print(f"error: need at least 3 configurations to hold any out "
              f"(found {n_c}); a split needs a train and a non-empty holdout",
              file=sys.stderr)
        return 1

    if args.budgets == "auto":
        lo, hi = 2, n_c - 1
        step = max(1, (hi - lo) // 8)
        budgets = sorted({b for b in range(lo, hi + 1, step)} | {hi})
    else:
        budgets = sorted({int(b) for b in args.budgets.split(",") if b.strip()})
    invalid = [b for b in budgets if b < 1 or b >= n_c]
    if invalid:
        print(f"error: budgets must satisfy 1 <= b < {n_c} (configurations "
              f"available); rejected {invalid}", file=sys.stderr)
        return 1

    sweep = run_heldout_experiments(
        matrix, configs, budgets, seed=args.seed, n_boot=args.n_boot
    )
    # JSON turns integer dict keys into strings, so the per-budget results are
    # emitted as a list carrying its own `budget` field. A consumer can then
    # index by budget without knowing the serialisation quirk.
    budget_rows = [
        {"budget": b, **sweep["budgets"][b]} for b in sorted(sweep["budgets"])
    ]
    out = {
        "registry": str(args.registry),
        "models": names,
        "configs": configs,
        "n_configs": n_c,
        "n_models": len(names),
        "n_per_cell": built["n_per_cell"],
        "n_missing_cells": built["n_missing_cells"],
        "excluded_models_lt2_cells": built["excluded_models_lt2_cells"],
        "budgets": budget_rows,
        "rank_instability": rank_instability_report(matrix, configs, names),
        "n_boot": args.n_boot,
        "base_seed": args.seed,
        "provenance": "DERIVED from committed registry rows; no new measurement",
        "reading_guide": (
            "For each budget b: fit on b configurations, predict the b rest. "
            "score_prediction_error_mae is mean |train mean - holdout mean| per "
            "model; pairwise_decision_accuracy is how often the model that won on "
            "train also won on holdout; ranking_recovery compares the train "
            "ranking to the holdout ranking. Rising error or falling accuracy "
            "means the matrix is too small to predict its own remainder."
        ),
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "heldout.json").write_text(_json.dumps(out, indent=2) + "\n", encoding="utf-8")

    md = [
        "# Held-out configuration generalization (DERIVED)",
        "",
        f"Source registry: `{args.registry}`. "
        f"{len(names)} models x {n_c} configurations "
        f"({built['n_missing_cells']} missing cell(s), left None).",
        "",
        "No new measurement: every value is derived from committed registry rows. "
        "For each budget the estimator is fit on the train configurations only; "
        "held-out configurations are used for evaluation and never for fitting.",
        "",
        "| runs spent | held out | score error (MAE) | rank recovery (kendall) | "
        "decision acc | decidable pairs |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for r in budget_rows:
        rr = r.get("ranking_recovery", {}) or {}

        def cell(v, digits=4):
            return "n/a" if v is None else f"{v:.{digits}f}"

        md.append(
            f"| {r['budget']} | {r['split']['n_heldout']} | "
            f"{cell(r.get('score_prediction_error_mae'))} | "
            f"{cell(rr.get('kendall_tau'), 3)} | "
            f"{cell(r.get('pairwise_decision_accuracy'), 3)} | "
            f"{r.get('n_decidable_pairs')} |"
        )
    md += [
        "",
        "score error (MAE): mean |train mean - holdout mean| accuracy, per model. "
        "rank recovery: Kendall tau between the train ranking and the holdout "
        "ranking. decision acc: how often the train winner is also the holdout "
        "winner, over pairs where both sides decide.",
        "",
        "Reading: a plateau near 0 error and 1.0 accuracy means the matrix already "
        "predicts its own remainder; values far from those are the honest cost of "
        "an under-sampled configuration space.",
        "",
        "## Rank instability across configurations",
        "",
        "| model A | model B | A wins | B wins | reversible | B wins only on |",
        "|---|---|---:|---:|---|---|",
    ]
    for p in out["rank_instability"]["pairs"]:
        if p["n_decidable"] == 0:
            continue
        flip = "yes" if p["reversible"] else "no"
        md.append(
            f"| {p['a']} | {p['b']} | {p['a_wins']} | {p['b_wins']} | {flip} | "
            f"{', '.join(p['b_wins_on']) or '—'} |"
        )
    md += [
        "",
        "A high decision accuracy above does NOT mean the ranking is safe. A "
        "reproducible minority of configurations can overturn an ordering without "
        "moving the majority vote, so the minority column is the one to read: those "
        "configuration keys are where a stable-looking ranking fails.",
    ]
    (out_dir / "heldout.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(_json.dumps({
        "models": names,
        "n_configs": n_c,
        "budgets": [r["budget"] for r in budget_rows],
        "paths": {"json": str(out_dir / "heldout.json"), "md": str(out_dir / "heldout.md")},
    }, indent=2, default=str))
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
    built = _registry_score_matrix(rows)
    matrix, names, configs = built["matrix"], built["models"], built["configs"]
    n_per_cell = built["n_per_cell"]
    for w in built["mixed_n_warnings"]:
        print(f"warning: mixed n (expected {w['expected']}, got {w['n']}); "
              f"comparability not guaranteed; run={w['run_id']}")
    reports = {}
    if len(names) >= 2 and n_per_cell:
        out = evaluation_reliability_score(
            matrix, n_per_cell=n_per_cell, n_boot=args.n_boot, seed=args.seed
        )
        out["n_per_cell"] = n_per_cell
        out["models"] = names
        out["n_configs_used"] = len(configs)
        out["n_missing_cells"] = built["n_missing_cells"]
        out["excluded_models_lt2_cells"] = built["excluded_models_lt2_cells"]
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


def _read_structured(path: str) -> dict:
    """Read a JSON or YAML spec without letting the caller guess the format."""
    from apertus_eval_prep.utils.serialization import read_json, read_yaml

    if str(path).endswith((".yaml", ".yml")):
        return read_yaml(path)
    payload = read_json(path)
    if isinstance(payload, list):
        return {"configurations": payload}
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a mapping or a list of configurations")
    return payload


def cmd_decision_stability(args: argparse.Namespace) -> int:
    """Does one declared policy select the same option everywhere?

    Nothing is measured here: the input is already-evaluated configurations, and
    the output is a derived diagnostic about how a *declared* policy behaves
    under them. The evidence tier is supplied by the caller and is never
    inferred upward, so a MOCK sweep cannot be reported as a real-model result.
    """
    import json as _json

    from apertus_eval_prep.decision import DecisionPolicy, decision_stability
    from apertus_eval_prep.utils.serialization import write_json

    payload = _read_structured(args.configurations)
    policy_spec = _read_structured(args.policy)
    # Config files in this repo wrap their block (`decision_policy:`); accept
    # both the wrapped and bare forms so the policy file stays a valid config.
    if "decision_policy" in policy_spec:
        policy_spec = policy_spec["decision_policy"]
    policy = DecisionPolicy.from_mapping(policy_spec)
    result = decision_stability(
        payload.get("configurations") or [],
        policy,
        baseline_config=args.baseline,
        evidence={"mode": args.evidence_mode},
    )
    if args.out:
        write_json(args.out, result)
    summary = {
        key: result.get(key)
        for key in (
            "status", "baseline_config", "baseline_decision", "valid_configurations",
            "same_decision", "stability", "stability_allowing_ties",
            "decision_reversals", "invalid_configurations", "reversal_cause_design",
        )
    }
    print(_json.dumps({"summary": summary, "out": args.out}, indent=2, default=str))
    return 0


def cmd_ranking_stability(args: argparse.Namespace) -> int:
    """Report every ordering-agreement metric separately, with no composite.

    The input is a score matrix already committed by earlier runs (one row per
    model, one column per configuration). A column with an unmeasured cell is
    reported as incomparable rather than being scored as zero.
    """
    import json as _json

    from apertus_eval_prep.ranking import ranking_stability_report
    from apertus_eval_prep.utils.serialization import write_json

    payload = _read_structured(args.matrix)
    models = payload.get("models")
    matrix = payload.get("matrix")
    if not isinstance(models, list) or not isinstance(matrix, list):
        raise ValueError("expected {models: [...], matrix: [[...], ...]}")
    if not matrix:
        raise ValueError("matrix is empty; there is nothing to compare")
    baseline_index = args.baseline_config
    if not 0 <= baseline_index < len(matrix[0]):
        raise ValueError(
            f"--baseline-config {baseline_index} is outside the {len(matrix[0])} available columns"
        )
    columns = list(zip(*matrix))
    report = ranking_stability_report(
        [str(m) for m in models],
        list(columns[baseline_index]),
        [list(column) for index, column in enumerate(columns) if index != baseline_index],
        k=args.k,
        evidence={"mode": args.evidence_mode},
    )
    report["baseline_column_index"] = baseline_index
    if args.out:
        write_json(args.out, report)
    print(_json.dumps({"summary": {
        key: report.get(key) for key in (
            "rank_reversal_rate", "top_1_stability", "top_k_stability",
            "mean_kendall_tau", "mean_pairwise_inversion_rate",
            "valid_perturbations", "incomparable_perturbations",
        )
    }, "out": args.out}, indent=2, default=str))
    return 0


def cmd_interactions(args: argparse.Namespace) -> int:
    """Factorial interaction analysis, or an explicit refusal to produce one.

    The command is deliberately able to return ``insufficient_design`` with no
    estimates. Running a main-effects analysis over OFAT data and reporting "no
    interaction found" is a null claim the design cannot support, so the
    artifact states the design kind at the top level instead.
    """
    import json as _json

    from apertus_eval_prep.factorial import analyse_interactions
    from apertus_eval_prep.utils.serialization import read_json, write_json

    payload = read_json(args.rows)
    rows = payload.get("rows") if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or not rows:
        raise ValueError("expected a non-empty list of scored rows")

    pairs: list[tuple[str, str]] = []
    for chunk in str(args.pairs).split(";"):
        names = [name.strip() for name in chunk.split(",") if name.strip()]
        if len(names) != 2:
            raise ValueError(
                f"pair {chunk!r} must name exactly two factors, e.g. 'prompt,backend'"
            )
        pairs.append((names[0], names[1]))

    report = analyse_interactions(
        rows,
        pairs,
        correction=args.correction,
        n_boot=args.n_boot,
        seed=args.seed,
        evidence={"mode": args.evidence_mode},
    )
    if args.out:
        write_json(args.out, report)
    print(_json.dumps({"summary": {
        key: report.get(key) for key in (
            "status", "design_kind", "n_pairs_measured", "n_pairs_requested",
            "n_effects_tested", "multiple_comparison_correction", "unavailable_pairs",
        )
    }, "interpretation": report["interpretation"], "out": args.out}, indent=2, default=str))
    return 0


def cmd_sensitivity(args: argparse.Namespace) -> int:
    """Evaluation sensitivity per factor, with ESI only against a declared scale.

    ESI is dimensionless, so it is only computed when the caller declares the
    unit it is measured in -- an explicit value or a Wilson half-width. Without
    one the artifact still reports absolute/relative deltas, the effect size and
    an interval, and leaves ``esi`` null with a reason.
    """
    import json as _json

    from apertus_eval_prep.sensitivity import factor_sensitivity_index, wilson_uncertainty_scale
    from apertus_eval_prep.utils.serialization import write_json

    rows = _read_records(args.rows, "rows")
    factors = [name.strip() for name in str(args.factors).split(",") if name.strip()]
    if not factors:
        raise ValueError("--factors must name at least one factor")
    scale = args.uncertainty_scale
    if args.wilson_scale:
        scale = wilson_uncertainty_scale(args.wilson_scale[0], int(args.wilson_scale[1]))

    report = factor_sensitivity_index(
        rows, factors, score_key=args.score_key, baseline_level=args.baseline_level,
        uncertainty_scale=scale, n_boot=args.n_boot, seed=args.seed,
        evidence={"mode": args.evidence_mode},
    )
    if args.out:
        write_json(args.out, report)
    print(_json.dumps({
        "status": report["status"],
        "most_sensitive_factor": report["most_sensitive_factor"],
        "uncertainty_scale": report["uncertainty_scale"],
        "factors": [
            {"factor": f["factor"], "status": f["status"],
             "absolute_delta": f.get("absolute_delta"),
             "relative_delta": f.get("relative_delta"), "esi": f.get("esi")}
            for f in report["factors"]
        ],
        "out": args.out,
    }, indent=2, default=str))
    return 0


def cmd_agent_regression(args: argparse.Namespace) -> int:
    """Compare two finished agent runs and apply a declared regression policy.

    Both inputs are already-committed run directories. The verdict is a *policy
    gate result*: it reports whether the candidate met a declared comparison
    policy, and a metric missing from either run is INCONCLUSIVE rather than
    allowed to pass.
    """
    import json as _json

    from apertus_eval_prep.agent_reliability import compare_agent_runs, evaluate_regression_policy
    from apertus_eval_prep.utils.serialization import read_json, write_json

    def _system(path: str) -> dict:
        candidate_path = Path(path) / "metrics.json"
        target = candidate_path if candidate_path.exists() else Path(path)
        if not target.exists():
            raise ValueError(f"{path}: no run directory or metrics.json found")
        payload = read_json(target)
        if not isinstance(payload, dict):
            raise ValueError(f"{target}: expected a metrics object")
        return dict(payload.get("system") or {})

    comparison = compare_agent_runs(
        _system(args.baseline), _system(args.candidate),
        baseline_id=str(args.baseline), candidate_id=str(args.candidate),
    )
    result: dict = {"comparison": comparison, "gate": None}
    if args.policy:
        spec = _read_structured(args.policy)
        result["gate"] = evaluate_regression_policy(
            comparison, spec.get("regression_policy", spec),
            evidence={"mode": args.evidence_mode},
        )
    else:
        result["gate_note"] = "no --policy given; this is a comparison, not a gate result"

    if args.out:
        write_json(args.out, result)
    gate = result.get("gate") or {}
    print(_json.dumps({
        "regressions": comparison["regressions"],
        "improvements": comparison["improvements"],
        "not_comparable": comparison["not_comparable"],
        "gate_result_type": gate.get("result_type"),
        "gate_status": gate.get("status"),
        "out": args.out,
    }, indent=2, default=str))
    return 0


def _read_records(path: str, key: str) -> list:
    """Read a list of records from a JSON/YAML file in either accepted shape.

    A bare list is used directly; a mapping is unwrapped from ``key``. Commands
    accepting both shapes need this because ``_read_structured`` normalises a
    bare list into a decision-stability envelope, which would otherwise be
    iterated key-by-key.
    """
    from apertus_eval_prep.utils.serialization import read_json, read_yaml

    if str(path).endswith((".yaml", ".yml")):
        payload = read_yaml(path)
    else:
        payload = read_json(path)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get(key), list):
        return list(payload[key])
    raise ValueError(f"{path}: expected a list of records or a '{key}' list")


def cmd_scenario_coverage(args: argparse.Namespace) -> int:
    """Report scenario coverage with declaration, execution and success apart."""
    import json as _json

    from apertus_eval_prep.agent_reliability import scenario_coverage
    from apertus_eval_prep.utils.serialization import write_json

    scenarios = _read_records(args.scenarios, "scenarios")
    outcomes: list = _read_records(args.outcomes, "outcomes") if args.outcomes else []
    result = scenario_coverage(scenarios, outcomes)
    if args.out:
        write_json(args.out, result)
    print(_json.dumps({"summary": {key: result.get(key) for key in (
        "declared_scenarios", "not_applicable_scenarios", "executed_scenarios",
        "succeeded_scenarios", "failed_scenarios", "untested_scenarios",
        "count_coverage", "execution_coverage", "success_rate_of_executed",
    )}, "out": args.out}, indent=2, default=str))
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


def cmd_site(args: argparse.Namespace) -> int:
    """Export one compact site.json for the research website (DERIVED)."""
    import json as _json

    from apertus_eval_prep.site import build_site, write_site

    root = repo_root()
    site = build_site(
        root, Path(args.registry),
        n_boot=args.n_boot, n_perm=args.n_perm, seed=args.seed,
    )
    path = write_site(site, Path(args.out))
    cov = site["coverage"]
    print(f"Wrote {path} "
          f"({cov['measured']}/{cov['planned_cells']} cells, "
          f"{site['statistics']['n_comparisons']} comparisons)")
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


def _platform_config(args: argparse.Namespace):
    from apertus_eval_prep.core.config import load_run_spec

    overrides = {}
    for item in getattr(args, "set", None) or []:
        if "=" not in item:
            raise SystemExit(f"--set expects dotted.path=value, got {item!r}")
        key, value = item.split("=", 1)
        try:
            overrides[key] = json.loads(value)
        except json.JSONDecodeError:
            overrides[key] = value
    spec = load_run_spec(Path(args.config), overrides)
    if getattr(args, "no_raw", False):
        spec.reporting.include_raw_outputs = False
    return spec


def cmd_platform_run(args: argparse.Namespace) -> int:
    from apertus_eval_prep.core.runner import run_evaluation

    result = run_evaluation(_platform_config(args), repo_root(), output_root=args.out,
                            run_id=args.run_id, command="apertus-eval-prep platform-run")
    print(json.dumps({"run_id": result.run_id, "directory": str(result.directory),
                      "quality": result.metrics.get("quality"),
                      "evidence_class": result.metrics.get("evidence_class"),
                      "evidence_mode": result.metrics.get("evidence_mode"),
                      "evidence": result.metrics.get("evidence")}, indent=2, default=str))
    return 0


def cmd_platform_matrix(args: argparse.Namespace) -> int:
    from apertus_eval_prep.experiments.matrix import run_experiment_matrix

    result = run_experiment_matrix(args.config, repo_root(), output_root=args.out,
                                   command="apertus-eval-prep platform-matrix")
    print(json.dumps(result.to_dict(), indent=2, default=str))
    return 0


def cmd_platform_compare(args: argparse.Namespace) -> int:
    from apertus_eval_prep.experiments.compare import compare_run_directories, comparison_markdown
    from apertus_eval_prep.utils.serialization import write_text

    out = Path(args.out)
    result = compare_run_directories(args.baseline, args.candidate, output=out.with_suffix(".json"))
    write_text(out.with_suffix(".md"), comparison_markdown(result))
    print(json.dumps(result, indent=2, default=str))
    return 0


def cmd_platform_episode(args: argparse.Namespace) -> int:
    from apertus_eval_prep.core.runner import run_evaluation

    result = run_evaluation(_platform_config(args), repo_root(), output_root=args.out,
                            run_id=getattr(args, "run_id", None), command="apertus-eval-prep platform-episode")
    print(json.dumps({"run_id": result.run_id, "directory": str(result.directory),
                      "system": result.metrics.get("system"), "evidence_class": result.metrics.get("evidence_class")}, indent=2))
    return 0


def cmd_platform_safety(args: argparse.Namespace) -> int:
    from apertus_eval_prep.safety.runner import run_safety_evaluation

    spec = _platform_config(args)
    if getattr(args, "baseline_run", None):
        spec.baseline_run = args.baseline_run
    result = run_safety_evaluation(spec, repo_root(), output_root=args.out,
                                   run_id=getattr(args, "run_id", None),
                                   command="apertus-eval-prep platform-safety")
    print(json.dumps({"run_id": result.run_id, "directory": str(result.directory),
                      "safety": result.metrics.get("safety"), "evidence_class": result.metrics.get("evidence_class")}, indent=2))
    return 0



def cmd_platform_report(args: argparse.Namespace) -> int:
    from apertus_eval_prep.reporting.platform import write_run_reports

    paths = write_run_reports(
        args.run,
        report_format=args.format,
        output_dir=args.out,
        baseline_run=getattr(args, "baseline_run", None),
    )
    print(json.dumps({key: str(value) if value else None for key, value in paths.items()}, indent=2))
    return 0


def cmd_platform_fingerprint(args: argparse.Namespace) -> int:
    from apertus_eval_prep.reporting.platform import write_failure_fingerprint

    path, fingerprint = write_failure_fingerprint(
        args.run, baseline_run=getattr(args, "baseline_run", None)
    )
    print(json.dumps({"path": str(path), "fingerprint": fingerprint}, indent=2, default=str))
    return 0


def cmd_platform_gate(args: argparse.Namespace) -> int:
    from apertus_eval_prep.core.artifacts import GATE_REPORT
    from apertus_eval_prep.release.gates import evaluate_release_gates
    from apertus_eval_prep.utils.serialization import read_json, read_yaml, write_json
    from apertus_eval_prep.utils.pii import redact_for_artifact

    run_dir = Path(args.run)
    metrics = read_json(run_dir / "metrics.json")
    rules = read_yaml(args.rules) if args.rules else {}
    decision = evaluate_release_gates(metrics, rules.get("release_gates", rules))
    safe_decision = redact_for_artifact(decision)
    write_json(run_dir / GATE_REPORT, safe_decision)
    metrics["release_gate"] = safe_decision
    write_json(run_dir / "metrics.json", redact_for_artifact(metrics))
    print(json.dumps(safe_decision, indent=2, default=str))
    return 0 if decision["status"] in {"PASS", "PASS_WITH_WATCHLIST"} else 2


def cmd_platform_export_review(args: argparse.Namespace) -> int:
    from apertus_eval_prep.review.export import export_review_package
    result = export_review_package(
        args.run, args.out, dimensions=args.dimensions, sample_size=args.sample_size,
        strategy=args.sampling_strategy, seed=args.seed, baseline_run=args.baseline_run,
        study_id=args.study_id, rubric_version=args.rubric_version,
    )
    print(json.dumps(result, indent=2, default=str))
    return 0


def cmd_platform_ingest_review(args: argparse.Namespace) -> int:
    from apertus_eval_prep.review.ingest import ingest_annotations
    result = ingest_annotations(args.input, args.out, study_id=args.study_id)
    print(json.dumps({k: v for k, v in result.items() if k != "annotations"}, indent=2, default=str))
    return 0


def cmd_platform_study_analyze(args: argparse.Namespace) -> int:
    from apertus_eval_prep.study.analysis import analyze_study
    from apertus_eval_prep.study.reporting import write_study_outputs
    from apertus_eval_prep.study.schema import load_study_config
    spec = load_study_config(args.study_config)
    summary = analyze_study(spec, args.runs, reviews=args.reviews)
    paths = write_study_outputs(summary, args.out)
    print(json.dumps({"paths": paths, "evidence_modes": summary.get("evidence_modes"), "real_model_evidence_available": summary.get("real_model_evidence_available")}, indent=2, default=str))
    return 0


def cmd_platform_ingest_runs(args: argparse.Namespace) -> int:
    from apertus_eval_prep.release.ingest import ingest_run_directories
    from apertus_eval_prep.utils.serialization import write_json

    result = ingest_run_directories(
        args.runs, allow_incompatible=bool(getattr(args, "allow_incompatible", False))
    )
    write_json(args.out, result)
    print(json.dumps(result, indent=2, default=str))
    return 0


def cmd_platform_select(args: argparse.Namespace) -> int:
    from apertus_eval_prep.release.deployment import compare_deployment_configurations
    from apertus_eval_prep.utils.serialization import read_json, write_json

    payload = read_json(args.points)
    points = payload.get("points", payload) if isinstance(payload, dict) else payload
    constraints = read_json(args.constraints) if args.constraints else None
    result = compare_deployment_configurations(points, constraints=constraints)
    if args.out:
        write_json(args.out, result)
    print(json.dumps(result, indent=2, default=str))
    return 0

def _add_platform_args(p: argparse.ArgumentParser, *, out_default: str | None = None) -> None:
    p.add_argument("--config", required=True, help="Typed platform YAML run spec.")
    p.add_argument("--out", default=out_default, help="Output root or report path.")
    p.add_argument("--set", action="append", help="Dotted config override, e.g. decoding.seed=2.")
    p.add_argument("--no-raw", dest="no_raw", action="store_true", help="Disable raw output retention.")


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

    p_heldout = sub.add_parser(
        "heldout",
        help="Held-out configuration generalization: predict unrun configs from run ones.",
    )
    p_heldout.add_argument("--registry", default="results/registry_paper.jsonl")
    p_heldout.add_argument("--out", default="reports/heldout")
    p_heldout.add_argument(
        "--budgets",
        default="auto",
        help="Comma-separated run counts to fit on, or 'auto' (default). "
             "Each must satisfy 1 <= b < number of configurations.",
    )
    p_heldout.add_argument("--n-boot", dest="n_boot", type=int, default=300)
    p_heldout.add_argument("--seed", type=int, default=0)
    p_heldout.set_defaults(func=cmd_heldout)

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

    p_decision = sub.add_parser(
        "decision-stability",
        help="Does a declared selection policy pick the same option under every configuration?",
    )
    p_decision.add_argument(
        "--configurations", required=True,
        help="JSON file: list of {configuration_id, factors, points} or {configurations: [...]}.",
    )
    p_decision.add_argument(
        "--policy", required=True, help="YAML/JSON policy file with objectives and constraints."
    )
    p_decision.add_argument(
        "--baseline", help="configuration_id to treat as baseline (default: the first entry)."
    )
    p_decision.add_argument("--out", default="reports/decision_stability/decision_stability.json")
    p_decision.add_argument(
        "--evidence-mode", dest="evidence_mode", default="UNKNOWN", choices=EVIDENCE_MODES,
        help="Evidence tier for the input. Declared explicitly; never inferred upward.",
    )
    p_decision.set_defaults(func=cmd_decision_stability)

    p_rank_stability = sub.add_parser(
        "ranking-stability",
        help="Ordering agreement across configurations: reversal rate, top-k, Kendall tau.",
    )
    p_rank_stability.add_argument(
        "--matrix", required=True,
        help="JSON file: {models: [...], matrix: [[score per config], ...]} with one row per model.",
    )
    p_rank_stability.add_argument(
        "--baseline-config", type=int, default=0,
        help="Column index of the baseline configuration (default: 0).",
    )
    p_rank_stability.add_argument("--k", type=int, default=1, help="Top-k for set stability (default: 1).")
    p_rank_stability.add_argument(
        "--out", default="reports/ranking_stability/ranking_stability.json"
    )
    p_rank_stability.add_argument(
        "--evidence-mode", dest="evidence_mode", default="UNKNOWN", choices=EVIDENCE_MODES,
        help="Evidence tier for the input. Declared explicitly; never inferred upward.",
    )
    p_rank_stability.set_defaults(func=cmd_ranking_stability)

    p_interactions = sub.add_parser(
        "interactions",
        help="Factorial interaction analysis: main effects, interaction, corrected p.",
    )
    p_interactions.add_argument(
        "--rows", required=True,
        help="JSON file: list of scored rows {<factor>: <level>, ..., 'score': float}.",
    )
    p_interactions.add_argument(
        "--pairs", required=True,
        help="Semicolon-separated factor pairs, e.g. 'prompt,backend;backend,quantization'.",
    )
    p_interactions.add_argument(
        "--correction", default="holm_bonferroni",
        choices=["holm_bonferroni", "benjamini_hochberg", "none"],
    )
    p_interactions.add_argument("--n-boot", dest="n_boot", type=int, default=0)
    p_interactions.add_argument("--seed", type=int, default=0)
    p_interactions.add_argument(
        "--out", default="reports/interactions/interactions.json"
    )
    p_interactions.add_argument(
        "--evidence-mode", dest="evidence_mode", default="UNKNOWN", choices=EVIDENCE_MODES,
        help="Evidence tier for the input. Declared explicitly; never inferred upward.",
    )
    p_interactions.set_defaults(func=cmd_interactions)

    p_sensitivity = sub.add_parser(
        "sensitivity",
        help="Evaluation Sensitivity Index per factor, against a declared scale.",
    )
    p_sensitivity.add_argument(
        "--rows", required=True,
        help="JSON file: list of scored rows {<factor>: <level>, ..., 'score': float}.",
    )
    p_sensitivity.add_argument("--factors", required=True, help="Comma-separated factor names.")
    p_sensitivity.add_argument("--score-key", dest="score_key", default="score")
    p_sensitivity.add_argument(
        "--baseline-level", dest="baseline_level",
        help="Level used as the relative-delta denominator (default: the lowest level).",
    )
    p_sensitivity.add_argument(
        "--uncertainty-scale", dest="uncertainty_scale", type=float,
        help="Declared ESI unit. Without it ESI is null rather than assumed.",
    )
    p_sensitivity.add_argument(
        "--wilson-scale", dest="wilson_scale", nargs=2, type=float, metavar=("ACC", "N"),
        help="Declare the scale as the Wilson 95%% half-width at accuracy ACC over N items.",
    )
    p_sensitivity.add_argument("--n-boot", dest="n_boot", type=int, default=500)
    p_sensitivity.add_argument("--seed", type=int, default=0)
    p_sensitivity.add_argument(
        "--out", default="reports/evaluation_sensitivity/sensitivity.json"
    )
    p_sensitivity.add_argument(
        "--evidence-mode", dest="evidence_mode", default="UNKNOWN", choices=EVIDENCE_MODES,
        help="Evidence tier for the input. Declared explicitly; never inferred upward.",
    )
    p_sensitivity.set_defaults(func=cmd_sensitivity)

    p_agent_regression = sub.add_parser(
        "agent-regression",
        help="Compare two agent runs and apply a declared regression policy.",
    )
    p_agent_regression.add_argument("--baseline", required=True, help="Baseline run directory.")
    p_agent_regression.add_argument("--candidate", required=True, help="Candidate run directory.")
    p_agent_regression.add_argument("--policy", help="YAML/JSON regression_policy file.")
    p_agent_regression.add_argument(
        "--out", default="reports/agent_regression/agent_regression.json"
    )
    p_agent_regression.add_argument(
        "--evidence-mode", dest="evidence_mode", default="UNKNOWN", choices=EVIDENCE_MODES,
        help="Evidence tier for the input runs. Declared explicitly; never inferred upward.",
    )
    p_agent_regression.set_defaults(func=cmd_agent_regression)

    p_scenario_coverage = sub.add_parser(
        "scenario-coverage",
        help="Scenario taxonomy coverage: declared, executed and succeeded separately.",
    )
    p_scenario_coverage.add_argument(
        "--scenarios", required=True,
        help="YAML/JSON with a 'scenarios' list of {scenario_id, scenario_class, applies}.",
    )
    p_scenario_coverage.add_argument(
        "--outcomes", help="Optional YAML/JSON list of {scenario_id, executed, succeeded}."
    )
    p_scenario_coverage.add_argument(
        "--out", default="reports/scenario_coverage/scenario_coverage.json"
    )
    p_scenario_coverage.set_defaults(func=cmd_scenario_coverage)

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

    p_site = sub.add_parser(
        "site",
        help="Export one compact site.json for the research website.",
    )
    p_site.add_argument("--registry", default="results/registry_paper.jsonl")
    p_site.add_argument("--out", default="reports/site")
    p_site.add_argument("--n-boot", dest="n_boot", type=int, default=500)
    p_site.add_argument("--n-perm", dest="n_perm", type=int, default=2000)
    p_site.add_argument("--seed", type=int, default=0)
    p_site.set_defaults(func=cmd_site)

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
    p_platform_run = sub.add_parser("platform-run", help="Run a typed offline/local evaluation and write an immutable artifact.")
    _add_platform_args(p_platform_run)
    p_platform_run.add_argument("--run-id", dest="run_id")
    p_platform_run.set_defaults(func=cmd_platform_run)

    p_platform_matrix = sub.add_parser("platform-matrix", help="Expand and run a deterministic experiment matrix.")
    _add_platform_args(p_platform_matrix)
    p_platform_matrix.set_defaults(func=cmd_platform_matrix)

    p_platform_compare = sub.add_parser("platform-compare", help="Compare two typed run directories with paired statistics.")
    p_platform_compare.add_argument("--baseline", required=True)
    p_platform_compare.add_argument("--candidate", required=True)
    p_platform_compare.add_argument("--out", required=True)
    p_platform_compare.set_defaults(func=cmd_platform_compare)

    p_platform_episode = sub.add_parser("platform-episode", help="Run a RAG/agent episode evaluation.")
    _add_platform_args(p_platform_episode)
    p_platform_episode.add_argument("--run-id", dest="run_id")
    p_platform_episode.set_defaults(func=cmd_platform_episode)

    p_platform_safety = sub.add_parser("platform-safety", help="Run the sanitized offline safety suite.")
    _add_platform_args(p_platform_safety)
    p_platform_safety.add_argument("--run-id", dest="run_id")
    p_platform_safety.add_argument("--baseline-run", dest="baseline_run", help="Optional prior safety run directory for aligned comparison.")
    p_platform_safety.set_defaults(func=cmd_platform_safety)

    p_platform_report = sub.add_parser("platform-report", help="Rebuild Markdown/HTML reports from an existing run.")
    p_platform_report.add_argument("--run", required=True, help="Run directory containing manifest.json and metrics.json.")
    p_platform_report.add_argument("--format", dest="format", choices=["markdown", "html", "both"], default="both")
    p_platform_report.add_argument("--out", help="Optional output directory; defaults to the run directory.")
    p_platform_report.add_argument("--baseline-run", dest="baseline_run")
    p_platform_report.set_defaults(func=cmd_platform_report)

    p_platform_fingerprint = sub.add_parser("platform-fingerprint", help="Rebuild failure_fingerprint.json from failures.jsonl.")
    p_platform_fingerprint.add_argument("--run", required=True)
    p_platform_fingerprint.add_argument("--baseline-run", dest="baseline_run")
    p_platform_fingerprint.set_defaults(func=cmd_platform_fingerprint)

    p_platform_gate = sub.add_parser("platform-gate", help="Evaluate release gates against an existing run.")
    p_platform_gate.add_argument("--run", required=True)
    p_platform_gate.add_argument("--rules", help="YAML release-gate rules.")
    p_platform_gate.set_defaults(func=cmd_platform_gate)

    p_export_review = sub.add_parser("platform-export-review", help="Export a sanitized JSONL human-review package from a run.")
    p_export_review.add_argument("--run", required=True)
    p_export_review.add_argument("--out", required=True)
    p_export_review.add_argument("--dimensions", nargs="+", default=None)
    p_export_review.add_argument("--sample-size", dest="sample_size", type=int, default=50)
    p_export_review.add_argument("--sampling-strategy", dest="sampling_strategy", choices=["random", "stratified", "priority"], default="stratified")
    p_export_review.add_argument("--seed", type=int, default=0)
    p_export_review.add_argument("--baseline-run", dest="baseline_run")
    p_export_review.add_argument("--study-id", default="REPLACE_WITH_STUDY_ID")
    p_export_review.add_argument("--rubric-version", default="phase8-v1")
    p_export_review.set_defaults(func=cmd_platform_export_review)

    p_ingest_review = sub.add_parser("platform-ingest-review", help="Validate completed review annotations and write a review summary.")
    p_ingest_review.add_argument("--input", required=True)
    p_ingest_review.add_argument("--out", required=True)
    p_ingest_review.add_argument("--study-id", dest="study_id")
    p_ingest_review.set_defaults(func=cmd_platform_ingest_review)

    p_study_analyze = sub.add_parser("platform-study-analyze", help="Aggregate compatible completed runs into a Phase 8 study report.")
    p_study_analyze.add_argument("--study-config", dest="study_config", required=True)
    p_study_analyze.add_argument("--runs", nargs="+", required=True)
    p_study_analyze.add_argument("--reviews")
    p_study_analyze.add_argument("--out", required=True)
    p_study_analyze.set_defaults(func=cmd_platform_study_analyze)

    p_platform_ingest = sub.add_parser(
        "platform-ingest-runs",
        help="Convert completed run artifacts into Phase 5 deployment comparison points.",
    )
    p_platform_ingest.add_argument("--runs", nargs="+", required=True, help="One or more run directories.")
    p_platform_ingest.add_argument("--out", required=True, help="Output comparison-points JSON file.")
    p_platform_ingest.add_argument(
        "--allow-incompatible", action="store_true",
        help="Record incompatible identities as warnings instead of rejecting the comparison.",
    )
    p_platform_ingest.set_defaults(func=cmd_platform_ingest_runs)

    p_platform_select = sub.add_parser("platform-select", help="Compare deployment points and apply constraints.")
    p_platform_select.add_argument("--points", required=True, help="JSON points file.")
    p_platform_select.add_argument("--constraints", help="JSON constraints file.")
    p_platform_select.add_argument("--out")
    p_platform_select.set_defaults(func=cmd_platform_select)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
