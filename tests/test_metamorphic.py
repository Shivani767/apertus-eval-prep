"""Tests for Phase 7-8: metamorphic eval + EvalFrag seed schema. Synthetic-first."""

import json
from pathlib import Path

from apertus_eval_prep.metamorphic import (
    Perturbation,
    PERTURBATION_FAMILIES,
    build_evalfrag_rows,
    load_paraphrase_groups,
    observed_summary,
    to_jsonl,
    transform_family,
    transform_formatting,
    transform_prefix,
    transform_suffix,
    validate_preservation,
)
from apertus_eval_prep.prompts import load_items

ROOT = Path(__file__).resolve().parents[1]


def _item(prompt: str = "Lea has 5 red apples and 7 green apples.\nHow many in total?"):
    return type(
        "I", (object,),
        {"id": "x1", "task": "gsm8k", "language": "en", "gold": "12", "prompt": prompt},
    )()


def test_transforms_preserve_gold_by_construction_and_are_deterministic():
    for family, fn in (("formatting", transform_formatting), ("instruction_prefix",
                                                              transform_prefix),
                       ("suffix_answer_request", transform_suffix)):
        a = transform_family("X?  Y\nZ", family)
        b = transform_family("X?  Y\nZ", family)
        assert a == b, f"{family} must be deterministic"
        assert a != "X?  Y\nZ", f"{family} must change the text"
    p = _item()
    rows = build_evalfrag_rows([p], max_per_family=1)
    assert len(rows) == 3
    assert all(r.gold == "12" and r.task == "gsm8k" for r in rows)
    assert all(r.perturbed_prompt != r.original_prompt for r in rows)
    assert all(validate_preservation(r) for r in rows)
    assert rows[0].expected_invariance.startswith("formatting")
    assert "designed inert" in rows[1].expected_invariance


def test_unknown_family_raises():
    import pytest

    with pytest.raises(ValueError, match="unknown perturbation family"):
        transform_family("x", "magic_family")
    with pytest.raises(ValueError, match="paraphrase"):
        build_evalfrag_rows([_item()], families=("paraphrase",))  # group-only


def test_paraphrase_groups_from_committed_data():
    groups = load_paraphrase_groups(ROOT / "data" / "paraphrase_set.jsonl")
    assert len(groups) == 8  # 4 stems x 2 wordings
    ids = {g.perturbation_id for g in groups}
    assert all(pid.split("::")[1] in ("p1", "p2") for pid in ids)
    assert all(g.family == "paraphrase" for g in groups)
    assert all(g.gold == g.gold for g in groups)
    assert all(g.perturbed_prompt != g.original_prompt for g in groups)
    assert all("designed" in g.expected_invariance for g in groups)


def test_evalfrag_seed_file_contract():
    path = ROOT / "data" / "evalfrag" / "evalfrag_seed.jsonl"
    assert path.exists()
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 12  # 4 tasks x 3 families
    from collections import Counter

    assert set(Counter((r["task"], r["family"]) for r in rows)) == {
        (t, f) for t in ("arc_easy", "gsm8k", "hellaswag", "mgsm")
        for f in ("formatting", "instruction_prefix", "suffix_answer_request")
    }
    assert all(r["observed"] is None for r in rows)  # PENDING, never fabricated
    assert all(r["expected_invariance"] for r in rows)
    assert {r["gold"] for r in rows} == {"A", "16", "3"}  # golds from frozen items


def test_observed_summary_pending_until_real_evidence():
    pending = [{"family": "formatting", "observed": None}]
    out = observed_summary(pending)
    assert out["status"] == "PENDING" and out["invariant_rate"] is None
    measured = [
        {"family": "formatting", "observed": {"correct": True}},
        {"family": "formatting", "observed": {"correct": False}},
        {"family": "instruction_prefix", "observed": {"correct": True}},
    ]
    out2 = observed_summary(measured)
    assert out2["status"] == "MEASURED" and out2["n_evidence"] == 3
    assert abs(out2["invariant_rate"] - 2 / 3) < 1e-4
    assert out2["by_family"]["formatting"]["n"] == 2


def test_jsonl_roundtrip_stable():
    p = _item()
    rows = build_evalfrag_rows([p], max_per_family=1)
    tmp = ROOT / ".pytest_tmp_evalfrag.jsonl"
    try:
        to_jsonl(rows, tmp)
        loaded = [json.loads(l) for l in tmp.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(loaded) == 3
        assert loaded[0]["source_item_id"] == "x1"
        assert loaded[0]["gold"] == "12"
    finally:
        if tmp.exists():
            tmp.unlink()