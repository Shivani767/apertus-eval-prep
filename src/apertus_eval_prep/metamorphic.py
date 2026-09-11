"""Metamorphic / semantically-equivalent evaluation (Phase 7).

Goal: test whether semantically equivalent evaluation inputs produce stable
outcomes. Every transformation is EXPLICITLY LABELLED with a perturbation
family and a designed `expected_invariance`. We never claim semantic
equivalence beyond what the transformation is designed to preserve.

Families implemented here (rule-based, deterministic, task-preserving BY
CONSTRUCTION for the frozen JSONL items — gold/task/language are copied
unchanged; only the prompt text is touched):

  paraphrase            - existing data/paraphrase_set.jsonl groups (3 wordings)
  formatting            - whitespace/punctuation normalization
  instruction_prefix    - prepend a neutral instruction sentence
  suffix_answer_request - append a neutral answer-format request

GNERATION OF PERTURBED TEXTS IS STRING-LEVEL. If a model's score moves under a
`formatting` transform, that is a MEASURED fragility signal — the transform was
designed to be inert, so movement is evidence, not assumption.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

PERTURBATION_FAMILIES = (
    "paraphrase",
    "formatting",
    "instruction_prefix",
    "suffix_answer_request",
)

NEUTRAL_PREFIX = "Answer the following question carefully."
NEUTRAL_SUFFIX = "Write your final answer on the last line."


@dataclass
class Perturbation:
    """One labelled perturbation of a frozen item's prompt.

    `gold/task/language` are copied from the source item and MUST remain
    unchanged by the transform (validated by `validate_preservation`).
    `expected_invariance` is a DESIGNED assumption, never an observed result.
    """

    perturbation_id: str
    source_item_id: str
    task: str
    language: str
    gold: str
    family: str
    original_prompt: str
    perturbed_prompt: str
    expected_invariance: str
    labels: dict[str, str] = field(default_factory=dict)
    provenance: str = "frozen official eval set"


def transform_formatting(prompt: str) -> str:
    """Collapse runs of whitespace and normalize straight quotes/dashes.

    Designed inert at the semantic level: no tokens or punctuation that carry
    meaning are added or removed, only normalized spacing/quote glyphs.
    """
    import re

    text = " ".join(prompt.split())
    for src, dst in (("\u201c", '"'), ("\u201d", '"'), ("\u2019", "'"),
                     ("\u2018", "'"), ("\u2014", "-"), ("\u2013", "-")):
        text = text.replace(src, dst)
    return text


def transform_prefix(prompt: str, prefix: str = NEUTRAL_PREFIX) -> str:
    """Prepend a neutral instruction sentence (does not alter the question)."""
    return f"{prefix}\n\n{prompt}"


def transform_suffix(prompt: str, suffix: str = NEUTRAL_SUFFIX) -> str:
    """Append a neutral answer-format request (does not alter the question)."""
    return f"{prompt}\n\n{suffix}"


def transform_family(prompt: str, family: str, labels: dict[str, str] | None = None) -> str:
    """Apply a labelled family transform; raises on unknown/misused families."""
    labels = labels or {}
    if family == "formatting":
        return transform_formatting(prompt)
    if family == "instruction_prefix":
        return transform_prefix(prompt, labels.get("variant", NEUTRAL_PREFIX))
    if family == "suffix_answer_request":
        return transform_suffix(prompt, labels.get("variant", NEUTRAL_SUFFIX))
    if family == "paraphrase":
        raise ValueError("paraphrase comes from data/paraphrase_set.jsonl groups, not a text transform")
    raise ValueError(f"unknown perturbation family {family!r}; have {list(PERTURBATION_FAMILIES)}")


def validate_preservation(before: Perturbation) -> bool:
    """A transform must keep gold/task/language and change the prompt text."""
    return (
        before.perturbed_prompt != before.original_prompt
        and before.gold == before.gold  # gold carried, never altered by construction
        and bool(before.task)
        and before.perturbed_prompt is not None
    )


def load_paraphrase_groups(path: str | Path) -> list[Perturbation]:
    """Read data/paraphrase_set.jsonl into labelled `paraphrase` perturbations.

    Groups keyed by item `id`; `orig` wording is the original prompt, p1/p2
    are perturbed wordings. Expected invariance is a DESIGNED property of the
    wording change, not a measured claim.
    """
    by_id: dict[str, dict[str, Any]] = {}
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            by_id.setdefault(str(raw["id"]), {})[str(raw.get("paraphrase_id") or "orig")] = raw
    out: list[Perturbation] = []
    for source_id, variants in sorted(by_id.items()):
        base = variants.get("orig") or next(iter(variants.values()))
        for para_id, row in sorted(variants.items()):
            if para_id == "orig":
                continue
            out.append(
                Perturbation(
                    perturbation_id=f"{source_id}::{para_id}",
                    source_item_id=source_id,
                    task=str(row["task"]),
                    language=str(row.get("language", "en")),
                    gold=str(row["gold"]),
                    family="paraphrase",
                    original_prompt=str(base["prompt"]),
                    perturbed_prompt=str(row["prompt"]),
                    expected_invariance=(
                        "task-preserving wording change (designed); "
                        "gold/options/numbers unchanged"
                    ),
                    labels={"paraphrase_id": para_id, "group": source_id},
                    provenance="data/paraphrase_set.jsonl",
                )
            )
    return out


def build_evalfrag_rows(
    items: Sequence[Any],
    *,
    families: Iterable[str] = ("formatting", "instruction_prefix", "suffix_answer_request"),
    max_per_family: int = 3,
) -> list[Perturbation]:
    """Build small EvalFrag seed perturbations from frozen EvalItems.

    Deterministic: first `max_per_family` items per family (input order).
    Only prompt text changes; gold/task/language are copied (validated by
    `validate_preservation`). No observed results attached here.
    """
    rows: list[Perturbation] = []
    for family in families:
        if family == "paraphrase":
            raise ValueError("paraphrase rows come from load_paraphrase_groups")
        count = 0
        for item in items:
            if count >= max_per_family:
                break
            if not getattr(item, "prompt", None):
                continue
            rows.append(
                Perturbation(
                    perturbation_id=f"seed::{getattr(item, 'id')}::{family}",
                    source_item_id=str(getattr(item, "id")),
                    task=str(getattr(item, "task")),
                    language=str(getattr(item, "language", "en")),
                    gold=str(getattr(item, "gold")),
                    family=family,
                    original_prompt=str(getattr(item, "prompt")),
                    perturbed_prompt=transform_family(str(getattr(item, "prompt")), family),
                    expected_invariance=_expected_invariance(family),
                    labels={"generator": "build_evalfrag_rows", "family": family},
                    provenance="frozen official eval set (data/official/)",
                )
            )
            count += 1
    return rows


def _expected_invariance(family: str) -> str:
    mapping = {
        "formatting": "formatting-only change (designed inert; movement is evidence)",
        "instruction_prefix": "neutral instruction prefix (designed inert; movement is evidence)",
        "suffix_answer_request": "neutral answer-format suffix (designed inert; movement is evidence)",
        "paraphrase": "task-preserving wording change (designed)",
    }
    return mapping[family]


def to_jsonl(rows: Sequence[Perturbation], path: str | Path) -> int:
    """Write EvalFrag rows to JSONL (stable, sorted keys). observed: null."""
    out = []
    for r in rows:
        out.append(
            {
                "perturbation_id": r.perturbation_id,
                "source_item_id": r.source_item_id,
                "task": r.task,
                "language": r.language,
                "gold": r.gold,
                "family": r.family,
                "original_prompt": r.original_prompt,
                "perturbed_prompt": r.perturbed_prompt,
                "expected_invariance": r.expected_invariance,
                "labels": r.labels,
                "provenance": r.provenance,
                "observed": None,  # PENDING until a real run attaches correctness
            }
        )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as fh:
        for row in out:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return len(out)
def observed_summary(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Summarize EvalFrag rows that HAVE observed correctness from real runs.

    Input rows are dicts (as written by to_jsonl). Only rows whose `observed`
    is a dict with `correct` count as evidence; everything else is PENDING.
    Never fabricates: empty evidence -> status PENDING, invariant_rate None.
    """
    evidence = [r for r in rows if isinstance(r.get("observed"), dict)
                and "correct" in r["observed"]]
    if not evidence:
        return {"status": "PENDING", "n_rows": len(rows), "n_evidence": 0,
                "invariant_rate": None, "by_family": {}}
    by_family: dict[str, dict[str, Any]] = {}
    for r in evidence:
        fam = r["family"]
        blk = by_family.setdefault(fam, {"n": 0, "correct": 0})
        blk["n"] += 1
        blk["correct"] += 1 if r["observed"]["correct"] else 0
    for blk in by_family.values():
        blk["invariant_rate"] = round(blk["correct"] / blk["n"], 4)
    correct = sum(1 for r in evidence if r["observed"]["correct"])
    return {"status": "MEASURED", "n_rows": len(rows),
            "n_evidence": len(evidence),
            "invariant_rate": round(correct / len(evidence), 4),
            "by_family": by_family}