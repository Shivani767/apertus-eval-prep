"""Tests for Pareto frontier analysis. Synthetic points only."""

from apertus_eval_prep.pareto import pareto_front, render_pareto_markdown


def test_frontier_classics():
    pts = [
        {"label": "A", "cost": 100, "acc": 0.80},
        {"label": "B", "cost": 200, "acc": 0.90},
        {"label": "C", "cost": 150, "acc": 0.75},  # dominated by A and B
        {"label": "D", "cost": 200, "acc": 0.80},  # dominated by B (same cost, lower acc)
    ]
    out = pareto_front(pts, x_key="cost", y_key="acc")
    assert [p["label"] for p in out["frontier"]] == ["A", "B"]
    assert sorted(p["label"] for p in out["dominated"]) == ["C", "D"]
    assert all(p["pareto"] == "frontier" for p in out["frontier"])
    assert out["excluded"] == []


def test_equal_points_are_both_frontier():
    pts = [
        {"label": "A", "cost": 100, "acc": 0.8},
        {"label": "B", "cost": 100, "acc": 0.8},
    ]
    out = pareto_front(pts, x_key="cost", y_key="acc")
    assert len(out["frontier"]) == 2 and out["dominated"] == []


def test_missing_coordinates_are_excluded_not_zero():
    pts = [
        {"label": "A", "cost": 100, "acc": 0.8},
        {"label": "B", "cost": None, "acc": 0.95},   # vLLM 0.0 case
        {"label": "C", "cost": 50, "acc": None},
    ]
    out = pareto_front(pts, x_key="cost", y_key="acc")
    assert [p["label"] for p in out["frontier"]] == ["A"]
    assert sorted(p["label"] for p in out["excluded"]) == ["B", "C"]
    assert all(p["pareto"] == "excluded" for p in out["excluded"])


def test_render_markdown_states_convention():
    pts = [{"label": "A", "cost": 1, "acc": 0.5}]
    out = pareto_front(pts, x_key="cost", y_key="acc")
    md = render_pareto_markdown(out)
    assert "lower `cost`" in md and "higher `acc`" in md
    assert "| A | 1 | 0.5 | frontier |" in md


def test_single_point_is_frontier():
    out = pareto_front([{"label": "solo", "c": 1, "q": 1}], x_key="c", y_key="q")
    assert out["frontier"][0]["label"] == "solo"
    assert out["dominated"] == []