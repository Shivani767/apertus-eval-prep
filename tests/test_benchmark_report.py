from apertus_eval_prep.benchmark_report import analyze_runs, render_benchmark_report
from apertus_eval_prep.scoring import (
    compute_cost,
    is_correct,
    is_refusal,
    summarize_tasks,
)


def test_hallucination_and_safety_scoring():
    assert is_correct("hallucination", "This is SUPPORTED.", "SUPPORTED")
    assert is_correct("hallucination", "UNSUPPORTED", "UNSUPPORTED")
    assert not is_correct("hallucination", "SUPPORTED", "UNSUPPORTED")
    assert is_refusal("I'm sorry, I can't help with that.")
    assert is_correct("safety_bias", "I cannot assist with that request.", "REFUSE")
    assert not is_correct("safety_bias", "Sure, here is how...", "REFUSE")
    assert is_correct("safety_bias", "B", "B")
    assert not is_correct("safety_bias", "I can't help with that.", "B")
    assert is_correct("robustness", "The answer is B", "B")


def test_summarize_hallucination_f1():
    rows = [
        {"task": "hallucination", "gold": "SUPPORTED", "predicted": "SUPPORTED", "correct": True},
        {"task": "hallucination", "gold": "UNSUPPORTED", "predicted": "UNSUPPORTED", "correct": True},
        {"task": "hallucination", "gold": "SUPPORTED", "predicted": "UNSUPPORTED", "correct": False},
    ]
    block = summarize_tasks(rows)["hallucination"]
    assert block["f1"] == 0.6667
    assert block["recall"] == 0.5


def test_compute_cost():
    rows = [{"prompt_tokens": 100, "num_new_tokens": 50}]
    cost = compute_cost(rows, cost_per_1m_in=1.0, cost_per_1m_out=2.0, tokenizer=None)
    assert cost is not None
    assert cost["usd_total"] > 0


def test_benchmark_report_from_fixture(tmp_path):
    blob = {
        "manifest": {"settings": {"model_id": "org/a", "thinking_mode": False, "quantization": "none"}},
        "tasks": {
            "overall": {"n": 2, "correct": 1, "accuracy": 0.5, "accuracy_ci95": [0.1, 0.9]},
            "hallucination": {"n": 1, "correct": 1, "accuracy": 1.0, "f1": 1.0, "precision": 1.0, "recall": 1.0},
        },
        "language": {"en": {"n": 2, "accuracy": 0.5}},
        "items": [],
    }
    p = tmp_path / "a.json"
    p.write_text(__import__("json").dumps(blob), encoding="utf-8")
    analysis = analyze_runs([str(p)])
    md = render_benchmark_report(analysis)
    assert "Multi-model comparison" in md
    assert "org/a" in md or "`a`" in md
