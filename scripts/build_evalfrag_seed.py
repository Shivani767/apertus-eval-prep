"""Generate the EvalFrag seed benchmark (Phase 8) from frozen official items.

Deterministic: reads data/official/eval_set.jsonl, takes the FIRST item of each
task family, applies labelled rule-based perturbations (formatting,
instruction_prefix, suffix_answer_request) via apertus_eval_prep.metamorphic,
and writes data/evalfrag/evalfrag_seed.jsonl. Observed results are null
(PENDING) — this script never attaches scores; real runs do.

Usage: python scripts/build_evalfrag_seed.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from apertus_eval_prep.metamorphic import (  # noqa: E402
    PERTURBATION_FAMILIES,
    build_evalfrag_rows,
    load_paraphrase_groups,
    observed_summary,
    to_jsonl,
)
from apertus_eval_prep.prompts import load_items  # noqa: E402

TASKS = ["arc_easy", "gsm8k", "hellaswag", "mgsm"]
OUT = ROOT / "data" / "evalfrag" / "evalfrag_seed.jsonl"
FAMILIES = ("formatting", "instruction_prefix", "suffix_answer_request")


def main() -> int:
    items = load_items(ROOT / "data" / "official" / "eval_set.jsonl", TASKS, limit=None)
    by_task: dict[str, list] = {}
    for it in items:
        by_task.setdefault(it.task, []).append(it)
    # One representative frozen item per task family (first in file order).
    selected = [by_task[t][0] for t in TASKS]
    print("source items:", [(i.task, i.id, i.gold) for i in selected])

    rows = []
    for item in selected:
        rows.extend(build_evalfrag_rows([item], families=FAMILIES, max_per_family=1))
    n_written = to_jsonl(rows, OUT)
    print(f"wrote {n_written} rows -> {OUT.relative_to(ROOT)}")
    summary = observed_summary([r.__dict__ for r in rows])
    print("observed summary:", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())