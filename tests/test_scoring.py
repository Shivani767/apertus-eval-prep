from apertus_eval_prep.scoring import (
    extract_mc_letter,
    extract_number,
    is_correct,
    percentile,
    summarize_tasks,
)


def test_mc_prefix_and_sentence():
    assert extract_mc_letter("B") == "B"
    assert extract_mc_letter("(C) photosynthesis") == "C"
    assert extract_mc_letter("The answer is D because gravity.") == "D"
    assert extract_mc_letter("") is None


def test_number_last_match():
    assert extract_number("She makes 18 dollars.") == "18"
    assert extract_number("16 - 3 - 4 = 9, 9 * 2 = 18") == "18"
    assert extract_number("area = 36.0 cm") == "36"
    assert extract_number("no digits") is None


def test_is_correct_by_task():
    assert is_correct("arc_easy", "B", "B")
    assert is_correct("template_canary", "The letter is A.", "A")
    assert is_correct("gsm8k", "Final: 18", "18")
    assert is_correct("multilingual", "insgesamt 12 Äpfel", "12")
    assert not is_correct("arc_easy", "Paris", "B")


def test_summarize_and_percentile():
    rows = [
        {"task": "arc_easy", "correct": True},
        {"task": "arc_easy", "correct": False},
        {"task": "gsm8k", "correct": True},
    ]
    summary = summarize_tasks(rows)
    assert summary["arc_easy"]["accuracy"] == 0.5
    assert summary["gsm8k"]["n"] == 1
    assert summary["overall"]["correct"] == 2
    assert percentile([10.0, 20.0, 30.0, 40.0], 0.5) == 25.0
