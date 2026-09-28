"""LLM-as-judge reliability: what a judge is, and what it is not.

The one invariant this module enforces is that a judge is **not ground truth**.
An LLM judge is an instrument with its own bias, variance and prompt
sensitivity, so its output is evidence *about the judge* until it has been
checked against something else. Nothing here emits a `HUMAN_VALIDATED` tier,
and `validate_judge_records` refuses a record that claims otherwise.

What is measured:

* **provenance** -- which judge, which revision, which prompt, which rubric,
  which temperature, and which position the candidate occupied. A judge result
  without these is not auditable, so they are required fields.
* **agreement** -- how often two judgments of the same item agree.
* **self-consistency** -- the spread when the same judge scores the same item
  repeatedly, which is the judge's own noise floor.
* **position bias** -- whether a candidate's score moves when it is swapped
  between slots of a pairwise comparison, measured by actually swapping rather
  than inferred from single-order data.
* **rubric sensitivity** -- whether the same pair under a different rubric gives
  a different verdict.

None of these are a claim about the candidates. They characterise the
instrument, and the artifact says so.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any, Mapping, Sequence

from apertus_eval_prep.core.evidence import normalize_evidence

JUDGE_SCHEMA_VERSION = "1.0"

JUDGE_DISCLAIMER = (
    "LLM-judge results describe an automated evaluator's behaviour on the "
    "records supplied. A judge is not ground truth: its output is evidence "
    "about the judge until validated against human annotation or another "
    "trusted reference. Nothing here is a human-validated result, a safety "
    "certification, or production approval."
)

#: Fields every judgment must carry to be analysable at all.
REQUIRED_JUDGE_FIELDS: tuple[str, ...] = (
    "item_id", "candidate_id", "judge_model", "judge_revision", "judge_prompt",
    "judge_temperature", "rubric_id", "verdict",
)

#: Verdict vocabulary. Kept small on purpose: a judge that must choose between
#: many labels is measuring its own taxonomy, not the candidates.
VERDICTS: tuple[str, ...] = ("correct", "incorrect", "tie")

#: Where a candidate sat in a pairwise comparison.
POSITIONS: tuple[str, ...] = ("A", "B")


class JudgeRecordError(ValueError):
    """Raised when a judgment record is missing provenance or malformed."""


def _verdict_score(verdict: str) -> float | None:
    """Map a verdict to a comparable score, or None when not comparable."""
    return {"correct": 1.0, "incorrect": 0.0, "tie": 0.5}.get(str(verdict))


def validate_judge_records(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate judgments, requiring full provenance on every record.

    A judgment without judge model, revision, prompt, temperature and rubric is
    not auditable: a reader could not tell what produced it. A record that
    claims to be human-validated is refused outright, because an automated judge
    cannot make that claim.
    """
    validated: list[dict[str, Any]] = []
    for index, raw in enumerate(records):
        record = dict(raw)
        missing = [f for f in REQUIRED_JUDGE_FIELDS if record.get(f) is None]
        if missing:
            raise JudgeRecordError(
                f"judgment {index} is missing required provenance: {missing}"
            )
        verdict = str(record["verdict"])
        if verdict not in VERDICTS:
            raise JudgeRecordError(
                f"judgment {index} has verdict {verdict!r}; expected one of {VERDICTS}"
            )
        if str(record.get("evidence_mode") or "").upper() == "HUMAN_VALIDATED":
            raise JudgeRecordError(
                "an automated judge record cannot be declared HUMAN_VALIDATED; "
                "human validation is established by review ingestion, not by "
                "a judge record"
            )
        position = record.get("position")
        if position is not None and str(position) not in POSITIONS:
            raise JudgeRecordError(
                f"judgment {index} has position {position!r}; expected one of {POSITIONS}"
            )
        record["verdict"] = verdict
        validated.append(record)
    return validated


def _self_consistency(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Spread of verdicts when the same judge scores the same item repeatedly."""
    groups: dict[tuple[str, str], list[float]] = defaultdict(list)
    for record in records:
        score = _verdict_score(record["verdict"])
        if score is not None:
            groups[(str(record["judge_model"]), str(record["item_id"]))].append(score)
    repeated = {k: v for k, v in groups.items() if len(v) > 1}
    if not repeated:
        return {
            "n_repeated_groups": 0,
            "mean_range": None,
            "unstable_groups": 0,
            "status": "INSUFFICIENT_DATA",
            "note": "no item was judged more than once, so the judge's own "
                    "variance is not observable from these records",
        }
    ranges = [max(v) - min(v) for v in repeated.values()]
    return {
        "n_repeated_groups": len(repeated),
        "mean_range": round(statistics.mean(ranges), 6),
        "unstable_groups": sum(1 for r in ranges if r > 0),
        "status": "MEASURED",
    }


def _position_bias(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Score differences attributable to the slot a candidate occupied.

    Only *swap* pairs are used: the same item and candidate judged in both
    positions by the same judge under the same rubric. A single-order dataset
    cannot reveal position bias, and must say so rather than report a number
    that looks like one.
    """
    seen: dict[tuple[str, str, str, str], dict[str, float]] = defaultdict(dict)
    for record in records:
        position = record.get("position")
        score = _verdict_score(record["verdict"])
        if position is None or score is None:
            continue
        key = (
            str(record["judge_model"]), str(record["item_id"]),
            str(record["candidate_id"]), str(record["rubric_id"]),
        )
        seen[key][str(position)] = score
    swaps = {k: v for k, v in seen.items() if set(v) == {"A", "B"}}
    if not swaps:
        return {
            "n_swap_pairs": 0,
            "mean_position_effect": None,
            "position_flipped": None,
            "status": "INSUFFICIENT_DATA",
            "note": "no candidate was judged in both positions, so position bias "
                    "is not observable; single-order data cannot reveal it",
        }
    effects = [v["A"] - v["B"] for v in swaps.values()]
    return {
        "n_swap_pairs": len(swaps),
        "mean_position_effect": round(statistics.mean(effects), 6),
        "position_flipped": sum(1 for e in effects if e != 0),
        "status": "MEASURED",
    }


def _rubric_sensitivity(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Whether the same item and candidate get the same verdict across rubrics."""
    seen: dict[tuple[str, str, str, str], dict[str, str]] = defaultdict(dict)
    for record in records:
        key = (
            str(record["judge_model"]), str(record["item_id"]),
            str(record["candidate_id"]), str(record.get("position") or "-"),
        )
        seen[key][str(record["rubric_id"])] = str(record["verdict"])
    multi = {k: v for k, v in seen.items() if len(v) > 1}
    if not multi:
        return {
            "n_multi_rubric_groups": 0,
            "rubric_disagreement": None,
            "status": "INSUFFICIENT_DATA",
            "note": "no judgment was repeated under a second rubric",
        }
    disagree = sum(1 for v in multi.values() if len(set(v.values())) > 1)
    return {
        "n_multi_rubric_groups": len(multi),
        "rubric_disagreement": round(disagree / len(multi), 6),
        "status": "MEASURED",
    }


def judge_reliability_analysis(
    records: Sequence[Mapping[str, Any]],
    *,
    reference_verdicts: Mapping[str, str] | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Characterise a judge from its records, without treating it as truth.

    ``records`` are judge judgments carrying full provenance (see
    ``REQUIRED_JUDGE_FIELDS``). ``reference_verdicts`` optionally maps
    ``item_id`` to a trusted verdict; when supplied, agreement against that
    reference is reported -- and even then it is described as agreement with a
    reference, never as correctness. Without a reference, no agreement figure is
    invented, because a judge agreeing with itself is not a measurement.
    """
    validated = validate_judge_records(records)
    result: dict[str, Any] = {
        "metric": "judge_reliability",
        "schema_version": JUDGE_SCHEMA_VERSION,
        "n_records": len(validated),
        "judges": sorted({str(r["judge_model"]) for r in validated}),
        "judge_revisions": sorted({str(r["judge_revision"]) for r in validated}),
        "rubrics": sorted({str(r["rubric_id"]) for r in validated}),
        "judge_prompts": sorted({str(r["judge_prompt"]) for r in validated}),
        "temperatures": sorted({float(r["judge_temperature"]) for r in validated}),
        "n_items": len({str(r["item_id"]) for r in validated}),
        "n_candidates": len({str(r["candidate_id"]) for r in validated}),
        "verdict_distribution": _distribution(validated),
        "self_consistency": _self_consistency(validated),
        "position_bias": _position_bias(validated),
        "rubric_sensitivity": _rubric_sensitivity(validated),
        "is_ground_truth": False,
        "ground_truth_note": (
            "An LLM judge is an instrument, not ground truth. These figures "
            "describe the judge's agreement with itself, under a swap test, and "
            "under alternative rubrics -- not the correctness of any candidate."
        ),
        "disclaimer": JUDGE_DISCLAIMER,
        "evidence": normalize_evidence(evidence),
    }
    if reference_verdicts is None:
        result["reference_agreement"] = {
            "status": "INSUFFICIENT_DATA",
            "agreement": None,
            "n_compared": 0,
            "note": "no human or trusted reference was supplied, so judge "
                    "agreement with a reference is not measured; the judge is "
                    "not treated as its own ground truth",
        }
    else:
        result["reference_agreement"] = _reference_agreement(validated, reference_verdicts)
    return result


def _distribution(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for record in records:
        counts[str(record["verdict"])] += 1
    return dict(sorted(counts.items()))


def _reference_agreement(
    records: Sequence[Mapping[str, Any]], reference: Mapping[str, str]
) -> dict[str, Any]:
    """Agreement with an external reference, described as agreement only."""
    agree = comparable = 0
    disagreements: list[dict[str, Any]] = []
    for record in records:
        expected = reference.get(str(record["item_id"]))
        if expected is None or str(expected) not in VERDICTS:
            continue
        comparable += 1
        if str(record["verdict"]) == str(expected):
            agree += 1
        else:
            disagreements.append({
                "item_id": record["item_id"],
                "candidate_id": record["candidate_id"],
                "judge_verdict": record["verdict"],
                "reference_verdict": str(expected),
            })
    if not comparable:
        return {
            "status": "INSUFFICIENT_DATA",
            "agreement": None,
            "n_compared": 0,
            "note": "no judged item had a comparable reference verdict",
        }
    return {
        "status": "MEASURED",
        "agreement": round(agree / comparable, 6),
        "n_compared": comparable,
        "n_agree": agree,
        "disagreements": disagreements,
        "note": "agreement with a reference; a high value is not proof of "
                "correctness, and agreement between two fallible sources is "
                "not validation",
    }


__all__ = [
    "JUDGE_DISCLAIMER",
    "JUDGE_SCHEMA_VERSION",
    "POSITIONS",
    "REQUIRED_JUDGE_FIELDS",
    "VERDICTS",
    "JudgeRecordError",
    "judge_reliability_analysis",
    "validate_judge_records",
]