"""Agreement statistics and adjudication queues for completed annotations."""
from __future__ import annotations

import math
from collections import defaultdict
from itertools import combinations
from typing import Any, Iterable, Mapping


def _key(record: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(record.get("run_id")), str(record.get("example_id") or record.get("episode_id")), str(record.get("dimension")))


def percent_agreement(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    grouped = defaultdict(list)
    for record in records:
        grouped[_key(record)].append((str(record.get("annotator_id_hash")), str(record.get("label"))))
    comparable = [labels for labels in grouped.values() if len({reviewer for reviewer, _ in labels}) >= 2]
    pairs = [(left[1], right[1]) for labels in comparable for left, right in combinations(dict.fromkeys(labels), 2)]
    if not pairs:
        return {"value": None, "status": "INSUFFICIENT_EVIDENCE", "n_items": 0, "n_comparisons": 0}
    return {
        "value": sum(left == right for left, right in pairs) / len(pairs),
        "status": "AVAILABLE", "n_items": len(comparable), "n_comparisons": len(pairs),
    }


def cohen_kappa(records: Iterable[Mapping[str, Any]], *, reviewers: tuple[str, str] | None = None) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str], dict[str, str]] = defaultdict(dict)
    for record in records:
        grouped[_key(record)][str(record.get("annotator_id_hash"))] = str(record.get("label"))
    usable = [labels for labels in grouped.values() if len(labels) >= 2]
    if not usable:
        return {"value": None, "status": "INSUFFICIENT_EVIDENCE", "limitations": ["at least two linked annotations are required"]}
    if reviewers is None:
        counts = sorted(len(row) for row in grouped.values() if len(row) >= 2)
        if not counts:
            return {"value": None, "status": "INSUFFICIENT_EVIDENCE", "limitations": ["at least two linked annotations are required"]}
        if any(count > 2 for count in counts):
            return {"value": None, "status": "NOT_AVAILABLE", "limitations": ["Cohen's kappa requires exactly two reviewers per item"]}
        reviewers = tuple(sorted({key for row in usable for key in row}))[:2]  # type: ignore[assignment]
    if len(reviewers) != 2 or reviewers[0] == reviewers[1]:
        return {"value": None, "status": "INCONCLUSIVE", "limitations": ["reviewer pair must contain two distinct identifiers"]}
    if reviewers[0] not in usable[0] or reviewers[1] not in usable[0]:
        return {"value": None, "status": "INSUFFICIENT_EVIDENCE", "limitations": ["reviewer pair has insufficient overlap"]}
    pairs = [(row[reviewers[0]], row[reviewers[1]]) for row in usable if reviewers[0] in row and reviewers[1] in row]
    if not pairs:
        return {"value": None, "status": "INSUFFICIENT_EVIDENCE", "limitations": ["no paired annotations"]}
    labels = sorted({label for pair in pairs for label in pair})
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    first = defaultdict(int); second = defaultdict(int)
    for a, b in pairs:
        first[a] += 1; second[b] += 1
    expected = sum((first[label] / n) * (second[label] / n) for label in labels)
    value = 1.0 if math.isclose(expected, 1.0) else (1 - observed) / (1 - expected)
    return {"value": value, "status": "AVAILABLE", "n_items": n, "reviewers": list(reviewers),
            "limitations": ["sensitive to class prevalence and should not be interpreted as proof of validity"]}


def fleiss_kappa(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Report Fleiss' kappa availability; no unsupported multi-rater estimate is claimed."""
    reviewers = {str(row.get("annotator_id_hash")) for row in records if row.get("annotator_id_hash")}
    return {"value": None, "status": "NOT_AVAILABLE" if len(reviewers) > 2 else "INSUFFICIENT_EVIDENCE",
            "method": "fleiss_kappa", "n_reviewers": len(reviewers),
            "limitations": ["Fleiss' kappa is not estimated by this lightweight workflow."]}


def score_correlation(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    pairs: list[tuple[float, float]] = []
    by_reviewer_item: dict[tuple[Any, str], dict[str, float]] = defaultdict(dict)
    for record in records:
        score = record.get("score")
        if score is None:
            continue
        by_reviewer_item[(_key(record), str(record.get("annotator_id_hash")))][str(record.get("annotator_id_hash"))] = float(score)
    grouped: dict[tuple[str, str, str], dict[str, float]] = defaultdict(dict)
    for (item, reviewer), values in by_reviewer_item.items():
        if values:
            grouped[item][reviewer] = next(iter(values.values()))
    for values in grouped.values():
        if len(values) >= 2:
            ordered = [values[key] for key in sorted(values)[:2]]
            pairs.append((ordered[0], ordered[1]))
    if len(pairs) < 2:
        return {"value": None, "status": "INSUFFICIENT_EVIDENCE", "method": "pearson", "n_pairs": len(pairs)}
    x = [a for a, _ in pairs]; y = [b for _, b in pairs]
    mx, my = sum(x) / len(x), sum(y) / len(y)
    num = sum((a - mx) * (b - my) for a, b in pairs)
    den = math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))
    return {"value": num / den if den else None, "status": "AVAILABLE" if den else "INSUFFICIENT_EVIDENCE",
            "method": "pearson", "n_pairs": len(pairs),
            "limitations": ["correlation does not establish annotation validity"]}


def agreement_summary(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(row) for row in records]
    by_dimension: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_dimension[str(row.get("dimension"))].append(row)
    queue: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_key(row)].append(row)
    for key, values in grouped.items():
        if len({str(row.get("label")) for row in values}) > 1:
            queue.append({"run_id": key[0], "item_id": key[1], "dimension": key[2], "status": "PENDING_ADJUDICATION"})
    return {
        "overall": {"percent_agreement": percent_agreement(rows), "cohen_kappa": cohen_kappa(rows),
                   "fleiss_kappa": fleiss_kappa(rows), "score_correlation": score_correlation(rows)},
        "by_dimension": {key: {
            "percent_agreement": percent_agreement(value), "cohen_kappa": cohen_kappa(value),
            "fleiss_kappa": fleiss_kappa(value), "score_correlation": score_correlation(value)
        } for key, value in sorted(by_dimension.items())},
        "disagreement_queue": queue,
        "limitations": ["Agreement measures consistency, not correctness, validity, or safety certification."],
    }


__all__ = ["agreement_summary", "cohen_kappa", "fleiss_kappa", "percent_agreement", "score_correlation"]
