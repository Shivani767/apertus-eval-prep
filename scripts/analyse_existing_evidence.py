#!/usr/bin/env python3
"""Run the three analyses that existing artifacts already support, with no new inference.

This driver exists because the interesting follow-ups need no GPU and no re-run: every
input is a file already committed to this repository. It performs three analyses that
are specified but not yet executed anywhere:

1. **Paired chat-template discordance.** Joins the per-item ``correct`` flags of
   ``results/hf_tokenizer.json`` and ``results/hf_none.json`` — identical settings
   except the one knob — and reports which items flipped, with an exact sign test on
   the discordant pairs. This is the item-level detail behind the aggregate delta
   recorded in ``docs/CHAT_TEMPLATE_EFFECT.md``.
2. **Factorial interaction decomposition** over the committed registry. The matrix is
   OFAT, so most factor pairs are expected to return ``UNAVAILABLE`` rather than a
   number; that is a result, not a failure, and it is reported as such.
3. **Leave-one-model-out generalization**: hide one model, fit on the rest, and report
   the hidden model's behaviour as an out-of-distribution target.

Every value written is DERIVED from committed rows. Nothing is imputed: a missing cell
stays missing, an untestable design reports UNAVAILABLE with a reason, and a model pair
that cannot decide is excluded rather than scored as a win.

Usage:
    python3 scripts/analyse_existing_evidence.py --out reports/existing_evidence
    python3 scripts/analyse_existing_evidence.py --out reports/existing_evidence --skip-lomo

Exit status is 0 when the run completes, even if some analyses are UNAVAILABLE: an
unavailable design is a finding, not an error. Deterministic given ``--seed``.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from apertus_eval_prep.heldout import leave_one_model_out_sweep  # noqa: E402
from apertus_eval_prep.registry import load_registry  # noqa: E402
from apertus_eval_prep.stats import wilson_interval  # noqa: E402
from apertus_eval_prep.variance import (  # noqa: E402
    decompose_variance,
    factorial_diagnostics,
    factorial_variance_decomposition,
)

TOKENIZER_RUN = ROOT / "results" / "hf_tokenizer.json"
NONE_RUN = ROOT / "results" / "hf_none.json"
REGISTRY = ROOT / "results" / "registry_paper.jsonl"


# ---------------------------------------------------------------------------
# 1. Paired chat-template discordance
# ---------------------------------------------------------------------------


def exact_sign_test(wins: int, losses: int) -> float | None:
    """Two-sided exact binomial (McNemar) p for discordant pairs under p=0.5.

    Written out rather than imported so the script depends only on the two pieces of
    statistics it can prove: the null is a fair coin, and
    ``P(X <= k) = sum C(n,i)/2^n``.
    """
    n = wins + losses
    if n == 0:
        return None
    tail = sum(math.comb(n, i) for i in range(0, min(wins, losses) + 1)) / (2 ** n)
    return round(min(1.0, 2 * tail), 6)


def template_discordance(tokenizer_path: Path, none_path: Path) -> dict[str, Any]:
    """Which items changed correctness between the two chat-template protocols."""
    with tokenizer_path.open(encoding="utf-8") as handle:
        templated = json.load(handle)
    with none_path.open(encoding="utf-8") as handle:
        raw = json.load(handle)

    left = {str(item["id"]): item for item in templated.get("items", [])}
    right = {str(item["id"]): item for item in raw.get("items", [])}
    shared = sorted(set(left) & set(right))
    missing = sorted(set(left) ^ set(right))

    flips: list[dict[str, Any]] = []
    per_task: dict[str, dict[str, int]] = {}
    for item_id in shared:
        a, b = left[item_id], right[item_id]
        task = str(a.get("task"))
        bucket = per_task.setdefault(task, {
            "n": 0, "templated_only": 0, "none_only": 0, "both_right": 0, "both_wrong": 0,
        })
        bucket["n"] += 1
        ca, cb = bool(a.get("correct")), bool(b.get("correct"))
        if ca and cb:
            bucket["both_right"] += 1
        elif not ca and not cb:
            bucket["both_wrong"] += 1
        elif ca and not cb:
            bucket["templated_only"] += 1
            flips.append({
                "id": item_id, "task": task, "flipped_to": "wrong_without_template",
                "gold": a.get("gold"),
                "templated_prediction": a.get("predicted"),
                "none_prediction": b.get("predicted"),
            })
        else:
            bucket["none_only"] += 1
            flips.append({
                "id": item_id, "task": task, "flipped_to": "right_without_template",
                "gold": a.get("gold"),
                "templated_prediction": a.get("predicted"),
                "none_prediction": b.get("predicted"),
            })

    templated_only = sum(1 for f in flips if f["flipped_to"] == "wrong_without_template")
    none_only = sum(1 for f in flips if f["flipped_to"] == "right_without_template")
    lo, hi = wilson_interval(templated_only + none_only, max(1, len(shared)))

    return {
        "provenance": "DERIVED from committed per-item records; no new measurement",
        "model": templated.get("manifest", {}).get("settings", {}).get("model_id"),
        "one_knob_changed": "chat_template (tokenizer vs none)",
        "n_shared_items": len(shared),
        "n_unmatched_items": len(missing),
        "unmatched_ids": missing,
        "discordant": {"templated_only_correct": templated_only, "none_only_correct": none_only},
        "exact_sign_test_p": exact_sign_test(templated_only, none_only),
        "discordant_fraction_ci95": [lo, hi],
        "per_task": per_task,
        "flipped_items": flips,
        "reading": (
            "An exact sign test on the discordant pairs. A large p means the item-level "
            "difference is consistent with per-item chance on this 28-item slice, which is "
            "why the effect is directional evidence rather than a precise magnitude."
        ),
    }


# ---------------------------------------------------------------------------
# 2 & 3. Registry-driven analyses
# ---------------------------------------------------------------------------


def registry_rows(registry_path: Path) -> list[dict[str, Any]]:
    """Scored registry rows reshaped for the variance analyses."""
    rows: list[dict[str, Any]] = []
    for record in load_registry(registry_path):
        overall = record.get("overall") or {}
        accuracy = overall.get("accuracy")
        if record.get("status") != "ok" or accuracy is None:
            continue
        rows.append({
            "model_id": record.get("model_id"),
            "factor": record.get("factor"),
            "factor_level": record.get("factor_level"),
            "score": float(accuracy),
        })
    return rows


def factorial_screen(rows: list[dict[str, Any]], *, n_boot: int, seed: int) -> dict[str, Any]:
    """One-way contributions plus a two-way screen for the designs worth trying.

    The registry is one-factor-at-a-time, so the honest expectation is that the
    two-way entries come back UNAVAILABLE. Reporting that is the point: it converts an
    admitted limitation into a measured one.
    """
    factors = sorted({str(r["factor"]) for r in rows if r.get("factor")})
    keys = {str(k) for r in rows for k in r}
    out: dict[str, Any] = {
        "n_scored_rows": len(rows),
        "one_way": decompose_variance(rows, factors),
        "two_way": {},
        "two_way_candidates": [],
    }
    # Only crossed designs are candidates. (model_id, factor) is the only pair
    # the registry can express: a model is measured at each factor level it
    # supports, but no two factors are ever varied together within a model, so
    # this is incomplete and the decomposition is expected to be UNAVAILABLE.
    # "prompt_id" is a *value* of `factor`, not a column, so that candidate is
    # skipped rather than silently producing something meaningless.
    for a, b in (("model_id", "factor"), ("model_id", "prompt_id")):
        if a not in keys or b not in keys:
            out["two_way_candidates"].append(
                {"pair": f"{a}×{b}", "status": "SKIPPED",
                 "reason": f"{b!r} is not a column in the registry rows"}
            )
            continue
        out["two_way_candidates"].append(
            {"pair": f"{a}×{b}", "status": "ATTEMPTED",
             "reason": "no two factors are varied together in an OFAT design, so "
                       "the (a,b) cells cannot form a complete balanced design"}
        )
        out["two_way"][f"{a}×{b}"] = {
            "diagnostics": factorial_diagnostics(rows, a, b),
            "decomposition": factorial_variance_decomposition(rows, a, b, n_boot=n_boot, seed=seed),
        }
    return out


def lomo_probe(registry_path: Path, *, budgets: list[int], seed: int) -> dict[str, Any]:
    """Leave-one-model-out generalization on the committed matrix.

    Reuses the CLI's matrix builder so the model set, cell semantics and the
    missing-cell rule are identical to the `heldout` command; a second builder here
    could drift and quietly produce a different set of models.
    """
    from apertus_eval_prep.cli import _registry_score_matrix

    built = _registry_score_matrix(load_registry(registry_path))
    matrix, models, configs = built["matrix"], built["models"], built["configs"]
    usable = [b for b in budgets if b < len(configs)]
    return {
        "provenance": "DERIVED; hidden model excluded from all fitting",
        "n_models": len(models),
        "n_configs": len(configs),
        "models": models,
        "budgets_requested": budgets,
        "budgets_dropped": [b for b in budgets if b >= len(configs)],
        "sweep": leave_one_model_out_sweep(matrix, configs, budgets=usable, seed=seed),
        "power": "low-power probe; three models meet the minimum of three",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="reports/existing_evidence")
    parser.add_argument("--registry", default=str(REGISTRY))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--n-boot", dest="n_boot", type=int, default=300)
    parser.add_argument("--budgets", default="2,4,6,8")
    parser.add_argument("--skip-template", action="store_true")
    parser.add_argument("--skip-lomo", action="store_true")
    args = parser.parse_args()

    budgets = [int(b) for b in args.budgets.split(",") if b.strip()]
    report: dict[str, Any] = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "registry": args.registry,
        "seed": args.seed,
        "n_boot": args.n_boot,
        "provenance": "DERIVED from committed artifacts; no model was executed",
        "analyses": {},
    }

    if not args.skip_template:
        if TOKENIZER_RUN.exists() and NONE_RUN.exists():
            report["analyses"]["template_discordance"] = template_discordance(TOKENIZER_RUN, NONE_RUN)
        else:
            report["analyses"]["template_discordance"] = {
                "status": "UNAVAILABLE",
                "reason": f"missing {TOKENIZER_RUN.name} or {NONE_RUN.name}",
            }

    rows = registry_rows(Path(args.registry))
    if rows:
        report["analyses"]["factorial"] = factorial_screen(rows, n_boot=args.n_boot, seed=args.seed)
        if not args.skip_lomo:
            report["analyses"]["leave_one_model_out"] = lomo_probe(
                Path(args.registry), budgets=budgets, seed=args.seed
            )

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "analysis.json").write_text(
        json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (out_dir / "analysis.md").write_text(_markdown(report), encoding="utf-8")
    print(json.dumps({
        "out": str(out_dir),
        "analyses": {
            key: ("UNAVAILABLE" if isinstance(v, dict) and v.get("status") == "UNAVAILABLE" else "ok")
            for key, v in report["analyses"].items()
        },
    }, indent=2))
    return 0


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Existing-evidence analysis (DERIVED)",
        "",
        f"Generated {report['generated_utc']} · seed {report['seed']} · "
        f"registry `{report['registry']}`",
        "",
        "No model was executed and no committed artifact was modified. Every value is "
        "derived from files already in this repository.",
        "",
    ]
    template = report["analyses"].get("template_discordance", {})
    if template.get("status") == "UNAVAILABLE":
        lines += ["## Chat-template discordance", "",
                  f"UNAVAILABLE: {template.get('reason')}", ""]
    elif template:
        lines += [
            "## Chat-template discordance (paired, one knob changed)",
            "",
            f"- shared items: {template['n_shared_items']} "
            f"(unmatched: {template['n_unmatched_items']})",
            f"- templated-only correct: {template['discordant']['templated_only_correct']}; "
            f"none-only correct: {template['discordant']['none_only_correct']}",
            f"- exact sign test p = {template['exact_sign_test_p']}",
            "",
            "| task | n | templated only | none only | both right | both wrong |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for task, bucket in sorted(template["per_task"].items()):
            lines.append(
                f"| {task} | {bucket['n']} | {bucket['templated_only']} | {bucket['none_only']} | "
                f"{bucket['both_right']} | {bucket['both_wrong']} |"
            )
        lines.append("")

    factorial = report["analyses"].get("factorial")
    if factorial:
        lines += ["## Factorial screen", "",
                  "| design | status | complete | balanced | reason |", "|---|---|---|---|---|"]
        for key, entry in factorial.get("two_way", {}).items():
            decomposition = entry["decomposition"]
            diagnostics = entry["diagnostics"]
            reason = decomposition.get("reason") or diagnostics.get("reason") or "-"
            lines.append(
                f"| {key} | {decomposition.get('status', 'MEASURED')} | "
                f"{diagnostics.get('complete')} | {diagnostics.get('balanced')} | {reason} |"
            )
        lines.append("")

    lomo = report["analyses"].get("leave_one_model_out")
    if lomo:
        lines += [
            f"## Leave-one-model-out ({lomo['power']})",
            "",
            f"models: {lomo['n_models']}, configurations: {lomo['n_configs']}, "
            f"budgets dropped as too large: {lomo['budgets_dropped']}",
            "",
            "| budget | hidden | visible | in-distribution decision acc | hidden std |",
            "|---:|---:|---:|---:|---:|",
        ]
        for budget, entry in lomo["sweep"]["budgets"].items():
            if entry.get("hidden_model_index") is None:
                lines.append(f"| {budget} | n/a | n/a | n/a | {entry.get('reason', '')} |")
                continue
            acc = entry["in_distribution_visible"]["pairwise_decision_accuracy"]
            std = entry["out_of_distribution_hidden"]["stability"]["std_all_configs"]
            lines.append(
                f"| {budget} | {entry['hidden_model_index']} | {entry['n_visible_models']} | "
                f"{'n/a' if acc is None else format(acc, '.3f')} | "
                f"{'n/a' if std is None else format(std, '.4f')} |"
            )
        lines.append("")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
