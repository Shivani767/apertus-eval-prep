from apertus_eval_prep.analysis import (
    build_pareto_from_runs,
    cost_performance_metrics,
    multilingual_analysis,
    ofat_delta,
    paraphrase_robustness,
    pareto_frontier,
    quantization_comparison,
    thinking_comparison,
)


def _run(acc: float, tokens: int = 100, ttft: float = 50.0, items: list | None = None) -> dict:
    items = items or [{"id": "a", "correct": acc >= 0.5}, {"id": "b", "correct": acc >= 0.5}]
    return {
        "tasks": {"overall": {"accuracy": acc, "n": len(items), "correct": sum(i["correct"] for i in items)}},
        "latency": {"ttft_ms_mean": ttft, "tokens_per_sec_mean": 10.0, "e2e_ms_mean": 200.0},
        "items": [{**it, "num_new_tokens": tokens // len(items)} for it in items],
        "cost": {"usd_total": 0.01},
    }


def test_thinking_comparison():
    nt = _run(0.5, tokens=80, items=[{"id": "x", "correct": True}, {"id": "y", "correct": False}])
    th = _run(0.6, tokens=120, items=[{"id": "x", "correct": True}, {"id": "y", "correct": True}])
    out = thinking_comparison(nt, th)
    assert out["reasoning_gain"] == 0.1
    assert out["additional_tokens"] == 40
    assert out["mcnemar"]["n"] == 2


def test_multilingual_analysis():
    block = {"en": {"accuracy": 0.9}, "de": {"accuracy": 0.7}, "fr": {"accuracy": 0.8}}
    out = multilingual_analysis(block)
    assert out["english_baseline"] == 0.9
    assert out["worst_language"] == "de"
    assert out["language_performance_gap"] == 0.2


def test_paraphrase_robustness():
    runs = [_run(0.8), _run(0.78), _run(0.82)]
    out = paraphrase_robustness(runs)
    assert out["n_variants"] == 3
    assert 0.0 <= out["robustness_score"] <= 1.0


def test_quantization_comparison():
    fp = _run(0.5, tokens=100)
    q = _run(0.48, tokens=100)
    out = quantization_comparison(fp, q, quant_label="int4")
    assert out["accuracy_delta"] == -0.02
    assert out["quantization"] == "int4"


def test_pareto_frontier():
    points = [
        {"label": "a", "accuracy": 0.9, "cost": 1.0},
        {"label": "b", "accuracy": 0.8, "cost": 0.5},
        {"label": "c", "accuracy": 0.85, "cost": 0.8},
    ]
    out = pareto_frontier(points, maximize=["accuracy"], minimize=["cost"])
    labels = {p["label"] for p in out["frontier"]}
    assert "b" in labels
    assert "a" in labels


def test_ofat_delta():
    c = _run(0.4, items=[{"id": "1", "correct": True}, {"id": "2", "correct": False}])
    t = _run(0.5, items=[{"id": "1", "correct": True}, {"id": "2", "correct": True}])
    out = ofat_delta(c, t)
    assert out["delta"] == 0.1
    assert out["mcnemar"]["a_wrong_b_correct"] == 1


def test_cost_performance_metrics():
    out = cost_performance_metrics(_run(0.7))
    assert out["accuracy_per_cost_estimated"] == 70.0
    assert out["cost_basis"] == "estimated_from_yaml_pricing"
