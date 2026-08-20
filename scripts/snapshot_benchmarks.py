#!/usr/bin/env python3
"""Download official splits, pin Hub revisions, write frozen JSONL.

Eval never calls Hugging Face datasets at scoring time. Re-run this script
only when you intentionally refresh the slice (then commit the new JSONL).

  pip install -e ".[snapshot]"
  python scripts/snapshot_benchmarks.py
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

N_EVAL = 200
N_FEWSHOT = 5
SHUFFLE_EVAL = 0
SHUFFLE_FEWSHOT = 1
LETTERS = "ABCD"

# Hub commit SHAs recorded at snapshot time. The script verifies them.
SOURCES = {
    "arc_easy": {
        "hf_id": "allenai/ai2_arc",
        "config": "ARC-Easy",
        "eval_split": "test",
        "fewshot_split": "train",
        "revision": "210d026faf9955653af8916fad021475a3f00453",
        "license": "CC-BY-SA-4.0",
        "task": "arc_easy",
        "language": "en",
    },
    "gsm8k": {
        "hf_id": "openai/gsm8k",
        "config": "main",
        "eval_split": "test",
        "fewshot_split": "train",
        "revision": "740312add88f781978c0658806c59bc2815b9866",
        "license": "MIT",
        "task": "gsm8k",
        "language": "en",
    },
    "hellaswag": {
        "hf_id": "Rowan/hellaswag",
        "config": None,
        "eval_split": "validation",
        "fewshot_split": "train",
        "revision": "218ec52e09a7e7462a5400043bb9a69a41d06b76",
        "license": "MIT",
        "task": "hellaswag",
        "language": "en",
    },
    "mgsm": {
        "hf_id": "juletxara/mgsm",
        "config": None,
        "eval_split": "test",
        "fewshot_split": "train",
        "revision": "b2f13d426afe3be8d69a7e739b36724db8b66bbc",
        "license": "MIT",
        "task": "mgsm",
        "language": "mixed",
        "mgsm_langs": ["en", "de", "fr"],
    },
}

_GSM_GOLD = re.compile(r"####\s*([-\d][\d,]*(?:\.\d+)?)")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _choices_block(labels: list[str], texts: list[str]) -> str:
    lines = []
    for label, text in zip(labels, texts):
        letter = label if label in LETTERS else LETTERS[len(lines)]
        lines.append(f"{letter}) {text.strip()}")
        if len(lines) == 4:
            break
    return "\n".join(lines)


def format_arc(row: dict, task: str, language: str, split: str) -> dict | None:
    choices = row.get("choices") or {}
    texts = list(choices.get("text") or [])
    labels = [str(x) for x in (choices.get("label") or [])]
    if not texts:
        return None
    key = str(row.get("answerKey") or "").strip()
    if key in "1234":
        key = LETTERS[int(key) - 1]
    if key not in LETTERS:
        return None
    q = str(row.get("question") or "").strip()
    orig = str(row.get("id") or "")
    return {
        "id": f"{task}/{split}/{orig or 'item'}",
        "task": task,
        "language": language,
        "gold": key,
        "prompt": f"{q}\n{_choices_block(labels, texts)}",
    }


def format_gsm8k(row: dict, task: str, language: str, idx: int, split: str) -> dict | None:
    question = str(row.get("question") or "").strip()
    answer = str(row.get("answer") or "")
    m = _GSM_GOLD.search(answer)
    if not m:
        return None
    gold = m.group(1).replace(",", "")
    if gold.endswith(".0"):
        gold = gold[:-2]
    return {
        "id": f"{task}/{split}/{idx:04d}",
        "task": task,
        "language": language,
        "gold": gold,
        "prompt": question,
    }


def format_hellaswag(row: dict, task: str, language: str, idx: int, split: str) -> dict | None:
    ctx = str(row.get("ctx") or "").strip()
    endings = list(row.get("endings") or [])
    if len(endings) < 4:
        return None
    label = row.get("label")
    try:
        li = int(label)
    except (TypeError, ValueError):
        return None
    if li < 0 or li > 3:
        return None
    block = _choices_block(list(LETTERS), [str(e) for e in endings[:4]])
    activity = str(row.get("activity_label") or "").strip()
    header = f"Activity: {activity}\n\n" if activity else ""
    return {
        "id": f"{task}/{split}/{idx:04d}",
        "task": task,
        "language": language,
        "gold": LETTERS[li],
        "prompt": f"{header}{ctx}\n\nWhich ending is most plausible?\n{block}",
    }


def format_mgsm(row: dict, task: str, language: str, idx: int, split: str) -> dict | None:
    question = str(row.get("question") or "").strip()
    gold = row.get("answer_number")
    if gold is None:
        gold = row.get("answer")
    if gold is None or not question:
        return None
    gold_s = str(gold).replace(",", "")
    if gold_s.endswith(".0"):
        gold_s = gold_s[:-2]
    return {
        "id": f"{task}/{split}/{language}_{idx:04d}",
        "task": task,
        "language": language,
        "gold": gold_s,
        "prompt": question,
    }


def _load(hf_id: str, config: str | None, split: str, revision: str):
    from datasets import load_dataset

    kwargs = dict(split=split, revision=revision)
    if config:
        return load_dataset(hf_id, config, **kwargs)
    return load_dataset(hf_id, **kwargs)


def _take(rows: list[dict], n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    order = list(range(len(rows)))
    rng.shuffle(order)
    picked = [rows[i] for i in order[:n]]
    return picked


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def snapshot_one(name: str, meta: dict, n_eval: int, n_few: int) -> tuple[list[dict], list[dict], str]:
    from huggingface_hub import dataset_info

    info = dataset_info(meta["hf_id"])
    sha = getattr(info, "sha", None) or meta["revision"]
    task = meta["task"]

    if name == "mgsm":
        eval_rows: list[dict] = []
        few_rows: list[dict] = []
        langs = meta["mgsm_langs"]
        per = max(1, n_eval // len(langs))
        leftover = n_eval - per * len(langs)
        few_each = [2, 2, 1]
        for i, lang in enumerate(langs):
            extra = 1 if i < leftover else 0
            ds_eval = _load(meta["hf_id"], lang, meta["eval_split"], meta["revision"])
            formatted = []
            for idx, row in enumerate(ds_eval):
                item = format_mgsm(dict(row), task, lang, idx, "eval")
                if item:
                    formatted.append(item)
            eval_rows.extend(_take(formatted, per + extra, SHUFFLE_EVAL + i))
            ds_few = _load(meta["hf_id"], lang, meta["fewshot_split"], meta["revision"])
            ff = []
            for idx, row in enumerate(ds_few):
                item = format_mgsm(dict(row), task, lang, idx, "few")
                if item:
                    ff.append(item)
            few_rows.extend(_take(ff, few_each[i], SHUFFLE_FEWSHOT + i))
        return eval_rows[:n_eval], few_rows[:n_few], str(sha)

    ds_eval = _load(meta["hf_id"], meta["config"], meta["eval_split"], meta["revision"])
    formatted_eval = []
    for idx, row in enumerate(ds_eval):
        raw = dict(row)
        if name == "arc_easy":
            item = format_arc(raw, task, meta["language"], "eval")
        elif name == "gsm8k":
            item = format_gsm8k(raw, task, meta["language"], idx, "eval")
        else:
            item = format_hellaswag(raw, task, meta["language"], idx, "eval")
        if item:
            formatted_eval.append(item)
    eval_rows = _take(formatted_eval, n_eval, SHUFFLE_EVAL)

    ds_few = _load(meta["hf_id"], meta["config"], meta["fewshot_split"], meta["revision"])
    formatted_few = []
    for idx, row in enumerate(ds_few):
        raw = dict(row)
        if name == "arc_easy":
            item = format_arc(raw, task, meta["language"], "few")
        elif name == "gsm8k":
            item = format_gsm8k(raw, task, meta["language"], idx, "few")
        else:
            item = format_hellaswag(raw, task, meta["language"], idx, "few")
        if item:
            formatted_few.append(item)
    few_rows = _take(formatted_few, n_few, SHUFFLE_FEWSHOT)
    return eval_rows, few_rows, str(sha)


def write_sources(out_dir: Path, recorded: dict[str, str], n_eval: int, n_few: int) -> None:
    lines = [
        "# Official frozen slices",
        "",
        "These JSONL files are the bench. Eval does not re-download them.",
        "Regenerate with `python scripts/snapshot_benchmarks.py` and commit.",
        "",
        f"Selection: shuffle with seed `{SHUFFLE_EVAL}` (eval) / `{SHUFFLE_FEWSHOT}` (few-shot),",
        f"then take first {n_eval} eval items and {n_few} few-shot items per task.",
        "MGSM is split across EN/DE/FR. MGSM few-shot comes from the official train",
        "split (8 exemplars/language), not from the scored test items.",
        "",
        "Protocol: **generative exact-match** (letter or last number). This is not",
        "lm-eval loglikelihood HellaSwag/ARC. Do not quote these numbers as leaderboard scores.",
        "",
        "| task | file | Hugging Face id | split | n | license | hub sha |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, meta in SOURCES.items():
        sha = recorded.get(name, meta["revision"])
        lines.append(
            f"| `{meta['task']}` | `{name}.jsonl` | `{meta['hf_id']}` "
            f"| {meta['eval_split']} | {n_eval} | {meta['license']} | `{sha}` |"
        )
    lines += [
        "",
        "Combined files: `eval_set.jsonl` (all eval items) and `fewshot.jsonl`.",
        "",
        "ARC-Easy: Clark et al., 2018, AI2. GSM8K: Cobbe et al., 2021.",
        "HellaSwag: Zellers et al., 2019. MGSM: Shi et al., 2022.",
        "",
    ]
    (out_dir / "SOURCES.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Snapshot official benchmark slices to JSONL.")
    parser.add_argument("--out-dir", default=str(repo_root() / "data" / "official"))
    parser.add_argument("--n-eval", type=int, default=N_EVAL)
    parser.add_argument("--n-fewshot", type=int, default=N_FEWSHOT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    combined_eval = out_dir / "eval_set.jsonl"
    if combined_eval.exists() and not args.force:
        print(f"{combined_eval} exists. Pass --force to overwrite.")
        return 0

    all_eval: list[dict] = []
    all_few: list[dict] = []
    recorded: dict[str, str] = {}
    for name, meta in SOURCES.items():
        print(f"snapshot {name} ...", flush=True)
        eval_rows, few_rows, sha = snapshot_one(name, meta, args.n_eval, args.n_fewshot)
        recorded[name] = sha
        _write_jsonl(out_dir / f"{name}.jsonl", eval_rows)
        _write_jsonl(out_dir / f"{name}_fewshot.jsonl", few_rows)
        print(f"  eval={len(eval_rows)} fewshot={len(few_rows)} sha={sha}", flush=True)
        all_eval.extend(eval_rows)
        all_few.extend(few_rows)

    _write_jsonl(combined_eval, all_eval)
    _write_jsonl(out_dir / "fewshot.jsonl", all_few)
    write_sources(out_dir, recorded, args.n_eval, args.n_fewshot)
    print(f"wrote {combined_eval} n={len(all_eval)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
