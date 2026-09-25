"""Rule-based quality evaluation for single-turn task outputs."""
from __future__ import annotations

from typing import Any, Mapping

from apertus_eval_prep.tasks.base import TaskExample


def normalize_answer(value: str, answer_format: str = "text") -> str:
    text = str(value or "").strip()
    if answer_format == "letter":
        return text[:1].upper() if text else ""
    if answer_format == "number":
        cleaned = "".join(ch for ch in text if ch.isdigit() or (ch == "-" and text.find(ch) == 0))
        try:
            return str(float(cleaned)) if "." in cleaned else str(int(cleaned))
        except ValueError:
            return cleaned
    return " ".join(text.lower().split())


def quality_score(example: TaskExample, output: str) -> dict[str, Any]:
    """Return a transparent normalized exact-match result."""
    fmt = str(example.metadata.get("answer_format", "text"))
    gold = normalize_answer(example.gold or "", fmt)
    predicted = normalize_answer(output, fmt)
    correct = bool(gold and predicted == gold)
    return {
        "score": 1.0 if correct else 0.0,
        "correct": correct,
        "predicted": predicted or None,
        "gold": gold or None,
        "scorer": "rules.normalized_exact_match",
        "answer_format": fmt,
    }


def is_refusal(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(marker in lowered for marker in ("i can't help", "i cannot help", "i'm sorry, but i can't"))


def score_response(example: TaskExample, output: str, *, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    result = quality_score(example, output)
    result["refusal"] = is_refusal(output)
    if metadata:
        result["metadata"] = dict(metadata)
    return result


__all__ = ["normalize_answer", "quality_score", "is_refusal", "score_response"]
