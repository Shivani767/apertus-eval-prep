"""Run the T4 factorial ground-truth experiment for ONE model (Stage gating).

Real inference happens ONLY here (free Colab T4 / or CPU). Everything else
(analyses, replay, figures) runs offline on CPU from the result registry.

Design: docs/t4_experiment_plan.md; study: configs/experiments/t4_factorial.yaml
Full design  = 3 prompts x 3 runtime levels (hf/none, hf/int8, vllm/none)
               x 3 seeds = 27. The 3x2x2 Cartesian (36) is structurally
               impossible: this harness refuses vllm x quantized by design.
Reduced      = same prompt x runtime grid with seeds [0, 1] = 18 (documented
               Stage-2 fallback; two complete 3x3 factorial replicates).

STAGE GATING (enforced here, not by config skips):
  --stage 1  only the Stage-1 ground-truth model (SmolLM2-1.7B-Instruct).
  --stage 2  confirmation models; REFUSES to start unless the Stage-1 model
             already has its full 36 ok-rows in the registry.

Resumability: every completed cell is appended to the registry immediately;
re-running skips status=="ok" cells (hash-based). Failed cells get an
explicit status=="failed" row and are retried on the next run.

Examples:
  python scripts/run_t4_research.py --stage 1 --dry-run
  python scripts/run_t4_research.py --stage 1 --model HuggingFaceTB/SmolLM2-1.7B-Instruct
  python scripts/run_t4_research.py --stage 2 --model Qwen/Qwen2.5-3B-Instruct --design reduced
  python scripts/run_t4_research.py --stage 1 --max-configs 12   # partial; marked

After any interruption simply re-run the same command: completed cells are
never re-executed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from apertus_eval_prep.registry import completed_hashes, load_registry
from apertus_eval_prep.sweep import (
    execute_factorial,
    expand_factorial_study,
    load_study,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
STUDY_PATH = REPO_ROOT / "configs" / "experiments" / "t4_factorial.yaml"

#: stage assignments mirror docs/t4_experiment_plan.md (Stage 1 first).
STAGE1_MODELS = ("HuggingFaceTB/SmolLM2-1.7B-Instruct",)
STAGE2_MODELS = (
    "Qwen/Qwen2.5-3B-Instruct",
    "microsoft/Phi-3.5-mini-instruct",
)
FULL_CONFIGS_PER_MODEL = 27   # 3 prompts x 3 runtime levels x 3 seeds
REDUCED_CONFIGS_PER_MODEL = 18  # same grid, seeds [0, 1] (documented fallback)


def stage_allows(stage: int, model_id: str) -> bool:
    """Is this model permitted in this stage?"""
    if stage == 1:
        return model_id in STAGE1_MODELS
    if stage == 2:
        return model_id in STAGE2_MODELS
    raise ValueError(f"stage must be 1 or 2, got {stage!r}")


def stage1_complete(registry_path: Path, design: str = "full") -> bool:
    """Stage gate: Stage-1 model has its full ok-row set in the registry."""
    needed = FULL_CONFIGS_PER_MODEL if design == "full" else REDUCED_CONFIGS_PER_MODEL
    rows = [r for r in load_registry(registry_path)
            if r.get("model_id") in STAGE1_MODELS]
    return len(completed_hashes(rows)) >= needed


def plan_for_model(
    study: dict,
    model_id: str,
    *,
    design: str = "full",
    max_configs: int | None = None,
) -> tuple[list[dict], list[str]]:
    """Cells for one model + integrity check (unique factor-level cells).

    Raises on duplicate configurations. --max-configs truncates AFTER the
    uniqueness check; the plan is then explicitly partial (the analyzer
    refuses partial designs as ground truth).
    """
    cells = [c for c in expand_factorial_study(study, design=design)
             if c["model_id"] == model_id]
    if not cells:
        raise SystemExit(
            f"no factorial cells for {model_id!r}; study models: {study['models']}"
        )
    seen: set[str] = set()
    for c in cells:
        level = c.get("factor_level", "")
        if level in seen:
            raise SystemExit(
                f"duplicate configuration detected: {level!r} appears twice; "
                "refusing to run an ambiguous design"
            )
        seen.add(level)
    expected = FULL_CONFIGS_PER_MODEL if design == "full" else REDUCED_CONFIGS_PER_MODEL
    if len(cells) != expected:
        raise SystemExit(
            f"design {design!r} produced {len(cells)} cells, expected {expected}; "
            "refusing to run a silently-changed design"
        )
    if max_configs is not None:
        cells = cells[:max_configs]
    return cells, [c.get("factor_level", "") for c in cells]


def _short_name(model_id: str) -> str:
    return model_id.split("/")[-1]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="T4 factorial ground-truth runner (one model per invocation)",
    )
    p.add_argument("--stage", type=int, choices=(1, 2), default=1,
                   help="1 = ground-truth model; 2 = confirmation models")
    p.add_argument("--model", required=True, help="HF model id")
    p.add_argument("--design", choices=("full", "reduced"), default="full",
                   help="full=27 configs/model; reduced=18 (Stage-2 fallback)")
    p.add_argument("--benchmark", default=None,
                   help="must match the study's frozen benchmark, e.g. arc_easy+gsm8k")
    p.add_argument("--output", default=None,
                   help="run-output dir (default results/t4/<short-model>)")
    p.add_argument("--registry", default="results/t4/registry_t4.jsonl")
    p.add_argument("--max-configs", type=int, default=None,
                   help="truncate the plan AFTER the uniqueness check (marks partial)")
    p.add_argument("--seed", type=int, default=0,
                   help="must equal the study control seed; the seed FACTOR levels "
                        "(0,1,2) are pinned by the design and never shifted")
    p.add_argument("--limit", type=int, default=None,
                   help="override per-task limit (development/smoke only)")
    p.add_argument("--dry-run", action="store_true", help="plan only; no inference")
    p.add_argument("--force", action="store_true", help="re-run completed cells")
    p.add_argument("--resume", action="store_true",
                   help="accepted for compatibility; resume is ALWAYS on "
                        "(hash-based skip of completed cells)")
    args = p.parse_args(argv)

    study = load_study(STUDY_PATH)
    study_benchmark = "+".join(study["tasks"])
    if args.benchmark is not None and args.benchmark != study_benchmark:
        raise SystemExit(
            f"--benchmark {args.benchmark!r} does not match the frozen study "
            f"benchmark {study_benchmark!r}; the design pins ONE benchmark"
        )
    if args.seed != int(study["control"].get("seed", 0)):
        raise SystemExit(
            f"--seed {args.seed} would shift the design; the seed factor levels "
            "are pinned in configs/experiments/t4_factorial.yaml"
        )
    if not stage_allows(args.stage, args.model):
        raise SystemExit(
            f"{args.model!r} is not a Stage-{args.stage} model "
            f"(stage1={STAGE1_MODELS}, stage2={STAGE2_MODELS})"
        )
    registry_path = Path(args.registry)
    if not registry_path.is_absolute():
        registry_path = REPO_ROOT / registry_path
    if args.stage == 2 and not args.dry_run and not stage1_complete(registry_path):
        raise SystemExit(
            "Stage-2 refusal: the Stage-1 ground-truth model does not yet have "
            "its complete configuration set in the registry. Finish Stage 1 "
            "first (docs/t4_experiment_plan.md)."
        )
    return _run_plan(args, study, registry_path)


def _run_plan(args, study, registry_path):
    cells, levels = plan_for_model(
        study, args.model, design=args.design, max_configs=args.max_configs,
    )
    done_before = 0
    if registry_path.exists():
        rows = [r for r in load_registry(registry_path)
                if r.get("model_id") == args.model]
        done_before = len(completed_hashes(rows))
    out_dir = Path(args.output) if args.output else (
        REPO_ROOT / "results" / "t4" / _short_name(args.model)
    )
    print(f"model            : {args.model}")
    print(f"stage / design   : {args.stage} / {args.design}")
    bench = "+".join(study["tasks"])
    print(f"benchmark        : {bench} (frozen slice, limit={study['limit']}/task)")
    print(f"planned configs  : {len(cells)}")
    print(f"already complete : {min(done_before, len(cells))}")
    if args.max_configs is not None and args.max_configs < len(levels):
        print("WARNING          : --max-configs truncates the design; this is an "
              "explicitly PARTIAL plan (never presented as ground truth)")
    if args.dry_run:
        print("dry-run          : planning only, no inference, no registry writes")
        for c in cells:
            print(f"  would run: {c.get('factor')} = {c.get('factor_level')}")
        return 0
    execute_factorial(
        STUDY_PATH, REPO_ROOT, out_dir, registry_path,
        design=args.design, limit=args.limit, dry_run=False,
        force=args.force, only_model=args.model, mark_failures=True,
    )
    rows = [r for r in load_registry(registry_path)
            if r.get("model_id") == args.model]
    ok = len(completed_hashes(rows))
    failed = sum(1 for r in rows if r.get("status") == "failed")
    total = len(cells)
    print("-" * 60)
    print(f"Progress: {min(ok, total)} / {total}")
    print(f"Completed: {min(ok, total)}")
    print(f"Remaining: {max(total - min(ok, total), 0)}")
    print(f"Failed: {failed}")
    print(f"Estimated remaining configurations: {max(total - min(ok, total), 0)}")
    if failed:
        print("failed cells carry explicit status='failed' rows and are retried "
              "on the next identical invocation")
    if ok < total:
        print("resume: re-run the SAME command; completed cells are never re-executed")
    print(f"registry         : {registry_path}")
    print(f"run outputs      : {out_dir}")
    return 0 if ok >= total else 1


if __name__ == "__main__":
    sys.exit(main())
