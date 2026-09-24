#!/usr/bin/env python
"""Offline analysis of real T4 research results (NO model loading, CPU only).

Reads a result registry (JSONL) produced by ``scripts/run_t4_research.py``,
reassembles the measured score table, and runs the research pipeline on it —
the same machinery validated on synthetic data by ``scripts/research_smoke.py``,
but driven by *measured* results:

  1. coverage / duplicate audit (registry integrity)
  2. adaptive budget replay: random vs OFAT vs Apertus-R (offline, free)
  3. guarded factorial variance decomposition per model
  4. held-out configuration reliability experiments
  5. pairwise ranking stability (rank-flip probabilities)
  6. leave-one-model-out generalization probe (>= 3 models only)

Everything reported here is labeled measured (from the registry). The script
never launches inference and never imports model backends.

Example:
    python scripts/analyze_research_results.py \
        --registry results/t4/registry_t4.jsonl \
        --experiment-id t4_factorial \
        --out reports/t4_analysis
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from apertus_eval_prep.adaptive import budget_curves
from apertus_eval_prep.heldout import (
    leave_one_model_out_sweep,
    run_heldout_experiments,
)
from apertus_eval_prep.variance import factorial_variance_decomposition

FACTOR_FIELDS = ("backend", "prompt_id", "quantization", "seed")


def parse_factor_level(level: str | None) -> dict[str, str]:
    """Parse 'backend=hf+prompt_id=p0+seed=0' -> dict (registry fast path)."""
    if not level:
        return {}
    out: dict[str, str] = {}
    for part in str(level).split("+"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def load_rows(registry: Path, experiment_id: str | None) -> list[dict]:
    rows = []
    with registry.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if experiment_id and row.get("experiment_id") != experiment_id:
                continue
            rows.append(row)
    return rows


def score_of(row: dict) -> float | None:
    overall = row.get("overall")
    if isinstance(overall, dict) and overall.get("accuracy") is not None:
        return float(overall["accuracy"])
    return None


def factor_levels(row: dict, repo_root: Path) -> dict[str, str]:
    """Factor levels per registry row; falls back to the run payload."""
    levels = parse_factor_level(row.get("factor_level"))
    if all(f in levels for f in FACTOR_FIELDS):
        return {f: levels[f] for f in FACTOR_FIELDS}
    path = row.get("path")
    if path:
        p = Path(path)
        if not p.is_absolute():
            p = repo_root / p
        if p.exists():
            payload = json.loads(p.read_text(encoding="utf-8"))
            settings = payload.get("manifest", {}).get("settings", {})
            got = {f: settings.get(f) for f in FACTOR_FIELDS}
            if all(v is not None for v in got.values()):
                return {f: str(v) for f, v in got.items()}
    return {}


def build_observations(
    rows: list[dict], repo_root: Path
) -> tuple[list[dict], list[dict]]:
    """(usable observations, problems) — problems reported, never silently dropped."""
    observations, problems = [], []
    for row in rows:
        if row.get("status") == "failed":
            problems.append({"run_id": row.get("run_id"),
                             "kind": "failed_run", "error": row.get("error")})
            continue
        if row.get("status") != "ok":
            problems.append({"run_id": row.get("run_id"),
                             "kind": f"unexpected status {row.get('status')!r}"})
            continue
        score = score_of(row)
        if score is None:
            problems.append({"run_id": row.get("run_id"), "kind": "no score"})
            continue
        levels = factor_levels(row, repo_root)
        missing = [f for f in FACTOR_FIELDS if f not in levels]
        if missing:
            problems.append({"run_id": row.get("run_id"),
                             "kind": f"missing factor levels: {missing}"})
            continue
        observations.append({
            "model_id": row["model_id"],
            "config_hash": row.get("config_hash"),
            "run_id": row.get("run_id"),
            "score": score,
            **{f: levels[f] for f in FACTOR_FIELDS},
        })
    return observations, problems


def config_key(obs: dict) -> str:
    return (f"p={obs['prompt_id']}|b={obs['backend']}|"
            f"q={obs['quantization']}|s={obs['seed']}")


def coverage_report(observations: list[dict], problems: list[dict]) -> dict:
    by_model: dict[str, list[dict]] = {}
    for obs in observations:
        by_model.setdefault(obs["model_id"], []).append(obs)
    per_model = {}
    for model, obs_list in sorted(by_model.items()):
        keys = [config_key(o) for o in obs_list]
        hashes = [o["config_hash"] for o in obs_list if o["config_hash"]]
        per_model[model] = {
            "n_configs_measured": len(obs_list),
            "n_unique_configs": len(set(keys)),
            "duplicate_config_keys": {k: n for k, n in Counter(keys).items() if n > 1},
            "duplicate_config_hashes": {h: n for h, n in Counter(hashes).items() if n > 1},
            "levels": {
                "backend": sorted({o["backend"] for o in obs_list}),
                "prompt_id": sorted({o["prompt_id"] for o in obs_list}),
                "quantization": sorted({o["quantization"] for o in obs_list}),
                "seed": sorted({o["seed"] for o in obs_list}),
            },
            "score_range": [min(o["score"] for o in obs_list),
                            max(o["score"] for o in obs_list)],
        }
    return {
        "n_registry_rows": len(observations) + len(problems),
        "n_usable_observations": len(observations),
        "n_problems": len(problems),
        "problems": problems,
        "per_model": per_model,
    }


def score_table(observations: list[dict]) -> dict[str, dict[str, float]]:
    table: dict[str, dict[str, float]] = {}
    for obs in observations:
        table.setdefault(obs["model_id"], {})[config_key(obs)] = obs["score"]
    return table


# ---------------------------------------------------------------------------
# Research analyses over the measured table
# ---------------------------------------------------------------------------


def variance_decompositions(observations: list[dict]) -> dict:
    """Guarded two-way decompositions per model for the three factor pairs."""
    pairs = [
        ("prompt_id", "backend"),
        ("prompt_id", "quantization"),
        ("backend", "quantization"),
    ]
    by_model: dict[str, list[dict]] = {}
    for obs in observations:
        by_model.setdefault(obs["model_id"], []).append(obs)
    out: dict[str, dict] = {}
    for model, obs_list in sorted(by_model.items()):
        rows = [{"score": o["score"], **{f: o[f] for f in FACTOR_FIELDS}}
                for o in obs_list]
        out[model] = {
            f"{a}x{b}": factorial_variance_decomposition(rows, a, b)
            for a, b in pairs
        }
    return out


def pairwise_ranking_stability(table: dict[str, dict[str, float]]) -> dict:
    """Per model pair: fraction of shared configs where the ordering flips (RQ3)."""
    models = sorted(table)
    out = {}
    for i in range(len(models)):
        for j in range(i + 1, len(models)):
            a, b = models[i], models[j]
            shared = sorted(set(table[a]) & set(table[b]))
            if len(shared) < 2:
                out[f"{a} vs {b}"] = {"n_shared_configs": len(shared),
                                      "status": "INSUFFICIENT"}
                continue
            wins = sum(1 for k in shared if table[a][k] > table[b][k])
            ties = sum(1 for k in shared if table[a][k] == table[b][k])
            p_hat = wins / len(shared)
            acc_a = sum(table[a][k] for k in shared) / len(shared)
            acc_b = sum(table[b][k] for k in shared) / len(shared)
            mean_flip = abs(acc_a - acc_b) == 0.0 or (
                (acc_a > acc_b) != (p_hat > 0.5) and ties < len(shared)
            )
            out[f"{a} vs {b}"] = {
                "n_shared_configs": len(shared),
                "a_wins_fraction": round(p_hat, 6),
                "tie_fraction": round(ties / len(shared), 6),
                "flip_probability": round(min(p_hat, 1.0 - p_hat) * 2, 6),
                "mean_ranking_reversal": bool(mean_flip),
                "label": "measured (within evaluated configuration space)",
            }
    return out


def heldout_reliability(table: dict[str, dict[str, float]], budgets: list[int],
                        seed: int, n_boot: int) -> dict:
    """Held-out configuration experiments on the measured matrix."""
    models = sorted(table)
    keys = sorted({k for m in models for k in table[m]})
    matrix = [[table[m].get(k) for k in keys] for m in models]
    usable = [b for b in budgets if b < len(keys)]
    dropped = [b for b in budgets if b >= len(keys)]
    result = run_heldout_experiments(matrix, keys, budgets=usable,
                                     seed=seed, n_boot=n_boot)
    result["note"] = ("estimator fit on train configs only; held-out configs "
                      "used for evaluation (leakage-free by construction)")
    if dropped:
        result["budgets_dropped"] = dropped
        result["drop_reason"] = "budget must be < n_configs for a holdout to exist"
    return result


def budget_replay(table: dict[str, dict[str, float]], budgets: list[int],
                  strategies: list[str], n_rep: int, seed: int) -> dict:
    """Offline strategy replay — every strategy gets the identical budget."""
    candidates = [{"model_id": m, "config_key": k}
                  for m in sorted(table) for k in sorted(table[m])]
    max_b = len(candidates)
    usable = [b for b in budgets if 1 <= b <= max_b]
    dropped = [b for b in budgets if b not in usable]
    out = budget_curves(table, candidates, budgets=usable,
                        strategies=tuple(strategies), n_rep=n_rep, seed=seed)
    if dropped:
        out["budgets_dropped"] = dropped
    out["n_candidates"] = max_b
    out["note"] = ("offline replay against the measured configuration table; "
                   "identical budgets across strategies; selection never sees "
                   "unobserved results (enforced by tests/test_research_integrity.py)")
    return out


def provenance_summary(rows: list[dict], observations: list[dict]) -> dict:
    commits = {r.get("git_commit") for r in rows if r.get("git_commit")}
    hw = Counter(str(r.get("hardware"))[:60] for r in rows if r.get("hardware"))
    stamps = sorted(r.get("utc") for r in rows if r.get("utc"))
    return {
        "git_commits": sorted(c for c in commits if c),
        "n_rows_missing_git_commit": sum(1 for r in rows if not r.get("git_commit")),
        "hardware_variants": dict(hw.most_common(3)),
        "first_result_utc": stamps[0] if stamps else None,
        "last_result_utc": stamps[-1] if stamps else None,
        "n_rows_missing_config_hash": sum(
            1 for o in observations if not o.get("config_hash")),
        "note": "null/unavailable metadata is reported, never fabricated",
    }


# ---------------------------------------------------------------------------
# Report assembly (CLI)
# ---------------------------------------------------------------------------


def leave_one_model_out_section(table: dict[str, dict[str, float]],
                                budgets: list[int], seed: int) -> dict:
    """LOMO generalization probe — only defined for >= 3 measured models."""
    models = sorted(table)
    if len(models) < 3:
        return {
            "status": "SKIPPED",
            "reason": f"leave-one-model-out needs >= 3 measured models, got {len(models)}",
        }
    keys = sorted({k for m in models for k in table[m]})
    matrix = [[table[m].get(k) for k in keys] for m in models]
    usable = [b for b in budgets if b < len(keys)]
    if not usable:
        return {"status": "SKIPPED",
                "reason": "no budget smaller than the configuration space"}
    out = leave_one_model_out_sweep(matrix, keys, budgets=usable, seed=seed)
    out["status"] = "MEASURED"
    out["label"] = ("generalization probe (held-out model = OOD); low power "
                    "with few models — descriptive, not definitive")
    return out


def render_markdown(report: dict) -> str:
    """Compact human-readable summary; every number is labeled measured."""
    lines: list[str] = []
    cov = report["coverage"]
    data_label = report["labels"]["data"]
    lines.append(f"# T4 research analysis (data label: {data_label})")
    lines.append("")
    lines.append(f"- registry: `{report['registry']}`")
    lines.append(f"- generated: {report['generated_utc']}")
    lines.append(f"- usable observations: {cov['n_usable_observations']} "
                 f"of {cov['n_registry_rows']} registry rows "
                 f"({cov['n_problems']} problems reported)")
    lines.append("")
    lines.append("## Configuration coverage per model")
    lines.append("")
    lines.append("| model | configs | unique | levels (b/p/q/s) |")
    lines.append("|---|---|---|---|")
    for model, pm in cov["per_model"].items():
        lv = pm["levels"]
        lines.append(
            f"| {model} | {pm['n_configs_measured']} | {pm['n_unique_configs']} "
            f"| {len(lv['backend'])}/{len(lv['prompt_id'])}/"
            f"{len(lv['quantization'])}/{len(lv['seed'])} |")
    lines.append("")
    lines.append("## Factorial variance decomposition (guarded ANOVA, per model)")
    lines.append("")
    for model, pairs in report["variance_decompositions"].items():
        for pair, d in pairs.items():
            if d["status"] != "MEASURED":
                lines.append(f"- {model} {pair}: {d['status']} — {d.get('reason')}")
                continue
            vf = d["variance_fractions"]
            lines.append(
                f"- {model} {pair}: A {vf['factor_a']:.3f}, B {vf['factor_b']:.3f}, "
                f"A×B {vf['interaction']:.3f}, residual {vf['residual']:.3f}")
    lines.append("")
    lines.append("## Pairwise ranking stability (within measured configs)")
    lines.append("")
    for pair, d in report["ranking_stability"].items():
        if d.get("status") == "INSUFFICIENT":
            lines.append(f"- {pair}: insufficient shared configs")
        else:
            lines.append(
                f"- {pair}: A wins {d['a_wins_fraction']:.3f} of "
                f"{d['n_shared_configs']} shared configs; "
                f"flip probability {d['flip_probability']:.3f}")
    lines.append("")
    br = report["budget_replay"]
    lines.append("## Budget replay (offline; identical budgets across strategies)")
    lines.append("")
    for b in br.get("budgets", []):
        parts = []
        for strat in sorted(br["curves"]):
            point = br["curves"][strat].get(str(b)) or br["curves"][strat].get(b)
            if point:
                v = point["values"]["ranking_recovery"]
                parts.append(f"{strat} {v['mean']:.3f} "
                             f"[{v['ci_lo']:.3f}, {v['ci_hi']:.3f}]")
        lines.append(f"- budget {b}: " + "; ".join(parts))
    lines.append("")
    hr = report["heldout_reliability"]
    lines.append("## Held-out configuration reliability (estimator: train only)")
    lines.append("")
    for b in sorted(hr.get("budgets", {}), key=str):
        e = hr["budgets"][b]
        rr = e["ranking_recovery"]
        lines.append(
            f"- budget {b}: decision acc {e['pairwise_decision_accuracy']}, "
            f"kendall {rr['kendall_tau']}, ECE {e['reliability_calibration']['ece']}, "
            f"CI coverage {e['ci_coverage']}")
    lines.append("")
    lomo = report["leave_one_model_out"]
    lines.append("## Leave-one-model-out (generalization probe)")
    lines.append("")
    if lomo.get("status") == "MEASURED":
        for b, e in sorted(lomo["budgets"].items(), key=lambda kv: str(kv[0])):
            if e.get("hidden_model_index") is None:
                lines.append(f"- budget {b}: {e.get('reason')}")
            else:
                ind = e["in_distribution_visible"]
                lines.append(
                    f"- budget {b}: hidden model #{e['hidden_model_index']}, "
                    f"visible decision acc {ind['pairwise_decision_accuracy']}")
    else:
        lines.append(f"- {lomo.get('status')}: {lomo.get('reason')}")
    lines.append("")
    prov = report["provenance"]
    lines.append("## Provenance")
    lines.append("")
    lines.append(f"- git commits: {prov['git_commits'] or 'none recorded'}")
    lines.append(f"- rows missing git commit: {prov['n_rows_missing_git_commit']}")
    lines.append(f"- window: {prov['first_result_utc']} .. {prov['last_result_utc']}")
    lines.append("")
    lines.append(f"_Data label: {data_label}. All tables/figures derived from the "
                 "registry at the path above; held-out rows are held-out, LOMO "
                 "rows are OOD probes. Ground truth means 'within the "
                 "evaluated configuration space'._")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Offline research analysis over a measured T4 registry "
                    "(CPU only; never loads models).")
    ap.add_argument("--registry", required=True, help="result registry JSONL")
    ap.add_argument("--experiment-id", default=None,
                    help="filter registry rows by experiment_id")
    ap.add_argument("--out", default="reports/t4_analysis",
                    help="output directory for analysis.json/.md")
    ap.add_argument("--budgets", default="5,10,15,20,25,30",
                    help="comma-separated replay/holdout budgets")
    ap.add_argument("--n-rep", type=int, default=20,
                    help="repetitions per strategy in the offline replay")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-boot", type=int, default=300,
                    help="bootstrap resamples for holdout CIs")
    ap.add_argument("--repo-root", default=".",
                    help="root for resolving relative result paths")
    ap.add_argument("--data-label", default="measured",
                    help="data label carried into the report (e.g. 'measured', "
                         "'synthetic'). Use 'synthetic' when validating the "
                         "pipeline on fixture data so nothing synthetic can "
                         "be mistaken for a measurement.")
    args = ap.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    registry = Path(args.registry)
    if not registry.exists():
        print(f"error: registry not found: {registry}")
        return 2
    budgets = sorted({int(b) for b in args.budgets.split(",") if b.strip()})
    strategies = ["random", "ofat", "apertus_r"]

    rows = load_rows(registry, args.experiment_id)
    observations, problems = build_observations(rows, repo_root)
    coverage = coverage_report(observations, problems)
    if not observations:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "coverage_problems.json").write_text(
            json.dumps(coverage, indent=2) + "\n", encoding="utf-8")
        print(f"error: no usable scored observations; "
              f"{coverage['n_problems']} problems written to "
              f"{out_dir / 'coverage_problems.json'}")
        return 1

    table = score_table(observations)
    print(f"loaded {len(observations)} observations (label: {args.data_label}) "
          f"across {len(table)} model(s); running offline analyses (CPU only)...")
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "registry": str(registry),
        "experiment_id": args.experiment_id,
        "labels": {
            "data": args.data_label,
            "scope": ("ground truth within the evaluated configuration space; "
                      "NOT universal ground truth"),
            "heldout": "held-out configurations (estimator never reads them)",
            "lomo": "held-out model = OOD generalization probe",
        },
        "coverage": coverage,
        "variance_decompositions": variance_decompositions(observations),
        "ranking_stability": pairwise_ranking_stability(table),
        "heldout_reliability": heldout_reliability(
            table, budgets, seed=args.seed, n_boot=args.n_boot),
        "budget_replay": budget_replay(
            table, budgets, strategies, n_rep=args.n_rep, seed=args.seed),
        "leave_one_model_out": leave_one_model_out_section(
            table, budgets, seed=args.seed),
        "provenance": provenance_summary(rows, observations),
    }
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "analysis.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md = render_markdown(report)
    (out_dir / "analysis.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"written: {out_dir / 'analysis.json'} and {out_dir / 'analysis.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


