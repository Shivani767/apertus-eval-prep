from apertus_eval_prep.report import ranking_table, paper_tables


def _blob(model: str, acc: float, n: int = 10, factor="control", level="control"):
    correct = int(round(acc * n))
    items = [{"id": f"i{i}", "task": "arc_easy", "correct": i < correct} for i in range(n)]
    return {
        "manifest": {"settings": {"model_id": model}},
        "tasks": {
            "overall": {
                "n": n,
                "correct": correct,
                "accuracy": round(correct / n, 4),
                "accuracy_ci95": [max(0.0, acc - 0.2), min(1.0, acc + 0.2)],
            }
        },
        "items": items,
        "_registry": {"factor": factor, "factor_level": level, "status": "ok"},
        "factor": factor,
        "factor_level": level,
    }


def test_ranking_tau_and_paper_tables():
    control = [
        _blob("org/big", 0.9),
        _blob("org/mid", 0.6),
        _blob("org/small", 0.3),
    ]
    flipped = [
        _blob("org/big", 0.3, factor="prompt_id", level="concise"),
        _blob("org/mid", 0.6, factor="prompt_id", level="concise"),
        _blob("org/small", 0.9, factor="prompt_id", level="concise"),
    ]
    analysis = ranking_table(control + flipped)
    assert analysis["control_ranking"][0]["model_id"] == "org/big"
    variant = next(r for r in analysis["by_config"] if r["factor"] == "prompt_id")
    assert variant["kendall_tau_vs_control"] == -1.0
    assert variant["rank_reversals_vs_control"] == 3
    md = paper_tables(analysis)
    assert "org/big" in md or "`big`" in md
    assert "tau" in md.lower() or "τ" in md
