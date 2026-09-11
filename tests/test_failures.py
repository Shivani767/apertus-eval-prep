"""Tests for the failure taxonomy. Synthetic items; one real-blob shape."""

from apertus_eval_prep.failures import (
    CATEGORIES,
    classify_item,
    failure_taxonomy,
    render_failure_markdown,
)


def _item(**over):
    base = {
        "id": "x/1", "task": "gsm8k", "correct": True,
        "predicted": "42", "gold": "42", "generation": "the answer is 42",
    }
    base.update(over)
    return base


def test_classify_all_categories():
    assert classify_item(_item()) == "correct"
    assert classify_item(_item(correct=False, predicted="41")) == "wrong_answer"
    assert classify_item(_item(correct=False, predicted=None)) == "unparseable"
    assert classify_item(_item(correct=False, predicted=None, generation="   ")) == "empty_output"
    assert classify_item(_item(generation=None, correct=False, predicted=None)) == "empty_output"
    assert classify_item(_item(error="cuda oom")) == "runtime_error"


def test_taxonomy_counts_and_rates():
    blob = {"items": [
        _item(id="a"),
        _item(id="b", correct=False, predicted="no"),
        _item(id="c", correct=False, predicted=None),
        _item(id="d", error="boom"),
        _item(id="e", task="trivia"),
    ]}
    rep = failure_taxonomy(blob)
    assert rep["total"] == 5
    assert rep["counts"] == {
        "runtime_error": 1, "empty_output": 0, "unparseable": 1,
        "wrong_answer": 1, "correct": 2,
    }
    assert abs(sum(rep["rates"][c] for c in CATEGORIES) - 1.0) < 1e-9
    assert abs(rep["failure_rate"] - 0.6) < 1e-9
    assert rep["per_task"]["gsm8k"]["total"] == 4
    assert rep["per_task"]["trivia"]["correct"] == 1


def test_taxonomy_empty_blob_is_all_zero_not_fabricated():
    rep = failure_taxonomy({"items": []})
    assert rep["total"] == 0
    assert all(v == 0 for v in rep["counts"].values())
    assert rep["failure_rate"] is None
    assert all(r is None for r in rep["rates"].values())


def test_missing_items_key_same_as_empty():
    assert failure_taxonomy({})["total"] == 0


def test_render_markdown():
    blob = {"items": [_item(), _item(correct=False, predicted="x")]}
    md = render_failure_markdown({"run1": failure_taxonomy(blob)})
    assert "## run1" in md
    assert "| wrong_answer | 1 | 0.5000 |" in md
    assert "| correct | 1 | 0.5000 |" in md