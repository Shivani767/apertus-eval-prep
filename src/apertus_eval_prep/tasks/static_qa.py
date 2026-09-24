"""Static question-answering task adapter."""
from __future__ import annotations

from typing import Any

from apertus_eval_prep.tasks.base import Task, TaskExample


class StaticQATask(Task):
    """Prompt-level QA task with rule-based normalized exact matching.

    The evaluator is intentionally conservative and auditable.  It does not use
    an external judge and returns the observed answer alongside the score.
    """

    kind = "static_qa"

    def metadata_for(self, example: TaskExample) -> dict[str, Any]:
        metadata = dict(example.metadata)
        metadata.setdefault("answer_format", _answer_format(example))
        if example.gold is not None:
            metadata.setdefault("oracle_answer", example.gold)
        return metadata

    def prompt_for(self, example: TaskExample) -> str:
        return example.prompt

    def score(self, example: TaskExample, output: str) -> dict[str, Any]:
        gold = example.gold
        predicted = _normalize(output, _answer_format(example))
        expected = _normalize(gold or "", _answer_format(example))
        correct = bool(expected and predicted == expected)
        return {
            "score": 1.0 if correct else 0.0,
            "correct": correct,
            "predicted": predicted or None,
            "gold": expected or None,
            "scorer": "normalized_exact_match",
        }


def _answer_format(example: TaskExample) -> str:
    value = example.metadata.get("answer_format")
    if value is not None:
        return str(value)
    if (example.gold or "").strip().upper() in {"A", "B", "C", "D"}:
        return "letter"
    if (example.gold or "").strip().lstrip("-").isdigit():
        return "number"
    return "text"


def _normalize(value: str, answer_format: str) -> str:
    text = str(value).strip()
    if answer_format == "letter":
        # Accept a labelled response such as ``B) oak`` while keeping the rule clear.
        return text[:1].upper() if text else ""
    if answer_format == "number":
        digits = "".join(ch for ch in text if ch.isdigit() or (ch == "-" and text.find(ch) == 0))
        try:
            return str(float(digits)) if "." in digits else str(int(digits))
        except ValueError:
            return digits
    return " ".join(text.lower().split())


__all__ = ["StaticQATask"]
