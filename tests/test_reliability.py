"""Tests for Phase 1-5 additions: result_schema, stability, ranking, factorial.

All fixtures are synthetic. No model downloads. No invented measurements.
"""

from pathlib import Path

from apertus_eval_prep import ranking, stability
from apertus_eval_prep.result_schema import (
    MEASURED,
    PENDING,
    SAMPLED,
    classify_row,
    coverage,
    enrich_run,
    load_enriched_registry,
    validate_enriched,
)
from apertus_eval_prep.sweep import expand_factorial, load_study

ROOT = Path(__file__).resolve().parents[1]


def _row(**kw):
    base = {
        "run_id": "m_control_abc",
        "config_hash": "abc",
        "experiment_id": "stability",
        "model_id": "org/m",
        "factor": "control",
        "factor_level": "control",
        "path": "results/runs/m_control_abc.json",
        "status": "ok",
    }
    base.update(kw)
    return base


def _blob(temp=0.0, acc=0.5, n=100):
    return {
        "manifest": {
            "utc": "2026-01-01T00:00:00Z",
            "git_commit": "deadbeef",
            "git_dirty": False,
            "packages": {"transformers": "9.9", "vllm": "1.0"},
            "hardware": {"gpu": "test"},
            "settings": {
                "model_id": "org/m",
                "revision": None,
                "backend": "hf",
                "temperature": temp,
                "prompt_id": "default",
                "seed": 0,
                "tasks": ["arc_easy"],
                "data_path": "data/official/eval_set.jsonl",
                "run_id": "m_control_abc",
            },
        },
        "tasks": {"overall": {"n": n, "correct": int(acc * n), "accuracy": acc,
                              "accuracy_ci95": [0.1, 0.9]}},
        "latency": {},
        "factor": "control",
        "factor_level": "control",
        "config_hash": "abc",
    }


def test_status_classification():
    assert classify_row(_row(), _blob(temp=0.0)) == MEASURED
    assert classify_row(_row(), _blob(temp=0.7)) == SAMPLED
    assert classify_row(_row(), None) == PENDING
    assert classify_row(_row(status="failed"), _blob()) == PENDING


def test_enrich_and_validate_roundtrip():
    view = enrich_run(_row(), _blob(temp=0.0, acc=0.6))
    assert view["status"] == MEASURED
    assert view["model"]["model_id"] == "org/m"
    assert view["metric"]["metric_value"] == 0.6
    assert view["provenance"]["artifact_path"].endswith(".json")
    assert validate_enriched(view) == []
    pending = enrich_run(_row(), None)
    assert pending["status"] == PENDING
    assert pending["metric"]["metric_value"] is None  # never zero-filled


def test_enriched_registry_matches_committed_counts():
    views = load_enriched_registry(ROOT / "results" / "registry_paper.jsonl", ROOT)
    assert len(views) == 31
    cov = coverage(views)
    assert cov["evidence"] == 31
    assert cov["by_status"][SAMPLED] == 6  # SmolLM2 x3 + Qwen-3B x3 measured
    assert cov["by_status"][MEASURED] == 25
    assert all(validate_enriched(v) == [] for v in views)


def test_stability_metrics_documented_behavior():
    assert abs(stability.score_range([0.5, 0.7, 0.6]) - 0.2) < 1e-9
    assert stability.score_range([0.5]) is None
    assert stability.coef_of_variation([0.0, 0.0]) is None  # mean 0: undefined, not 0
    assert stability.cohens_h(0.5, 0.5) == 0.0
    assert stability.cohens_h(1.5, 0.5) is None
    boot = stability.bootstrap_ci_mean([0.4, 0.5, 0.6], n_boot=500, seed=0)
    assert boot["lo"] <= boot["mean"] <= boot["hi"]
    assert stability.bootstrap_ci_mean([0.4, 0.5, 0.6], n_boot=500, seed=0) == boot
    pd = stability.paired_difference({"a": True, "b": False}, {"a": True, "c": True})
    assert pd["n_paired"] == 1 and pd["n_dropped"] == 2
    sens = stability.factor_sensitivity({"x": [0.5], "y": [0.7], "z": []})
    assert abs(sens["max_abs_delta"] - 0.2) < 1e-9 and sens["empty_levels"] == ["z"]


def test_ranking_layer():
    # 3 models x 3 configs; model 0 always best, models 1/2 flip once.
    matrix = [[0.9, 0.8, 0.9], [0.6, 0.7, 0.5], [0.5, 0.6, 0.6]]
    assert ranking.spearman_rank_correlation([1, 2, 3], [1, 2, 3]) == 1.0
    assert ranking.spearman_rank_correlation([0.5, 0.5], [0.5, 0.5]) is None
    wins = ranking.pairwise_win_rates(matrix)
    assert wins[0][1] == 1.0 and wins[1][0] == 0.0
    assert 0.0 < wins[1][2] < 1.0
    dists = ranking.rank_distributions(matrix)
    assert dists[0]["p_rank_1"] == 1.0 and dists[0]["mean_rank"] == 1.0
    assert dists[1]["rank_variance"] > 0
    boot = ranking.bootstrap_ranking_stability(matrix, n_boot=200, seed=0)
    assert 0.0 <= boot["mean_tau"] <= 1.0
    assert ranking.bootstrap_ranking_stability(matrix, n_boot=200, seed=0) == boot


def test_bootstrap_ranking_stability_sparse_matrix():
    # Regression: ref_acc used positional indices instead of usable column
    # indices, crashing (or silently mis-meaning) on matrices with None cells.
    sparse = [
        [0.9, None, 0.9, 0.8],
        [0.6, 0.7, None, 0.6],
        [0.5, 0.6, 0.6, None],
    ]
    boot = ranking.bootstrap_ranking_stability(sparse, n_boot=100, seed=0)
    assert boot["n_configs"] == 1  # only col 0 is fully measured
    assert boot["mean_tau"] is not None
    assert ranking.bootstrap_ranking_stability(sparse, n_boot=100, seed=0) == boot
    # reference ranking from the single usable column, hand-checkable:
    # means (0.9, 0.6, 0.5) -> ranks (1, 2, 3); every resample draws col 0,
    # so tau must be exactly 1.0 and no reversal possible.
    assert boot["mean_tau"] == 1.0
    assert boot["p_any_reversal"] == 0.0


def test_factorial_design_and_budget():
    study = load_study(ROOT / "configs" / "experiments" / "stability.yaml")
    cells = expand_factorial(
        study, {"prompt_id": ["concise", "5shot"], "backend": ["hf", "vllm"]},
        include_control=False, max_cells=100,
    )
    assert all(c.get("design") == "factorial" for c in cells)
    assert all(c["factor"] == "backendxprompt_id" for c in cells)
    import pytest

    with pytest.raises(ValueError, match="budget"):
        expand_factorial(
            study, {"prompt_id": ["concise", "5shot"], "backend": ["hf", "vllm"]},
            max_cells=2,
        )
    sel = expand_factorial(
        study, {"prompt_id": ["concise", "5shot"]},
        only_combos=[{"prompt_id": "concise"}], include_control=False,
    )
    assert {c["prompt_id"] for c in sel} == {"concise"}
