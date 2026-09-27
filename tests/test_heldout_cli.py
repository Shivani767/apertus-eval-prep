"""The held-out budget command must be reachable, honest, and deterministic.

The held-out experiment asks how many configurations a team must run before the
matrix can predict the configurations they skipped. That is only a useful claim
if the command exists, refuses impossible budgets instead of quietly returning a
flattering number, keeps missing cells missing, and never leaks held-out data
into the fit.
"""

from __future__ import annotations

import json

from apertus_eval_prep.cli import _registry_score_matrix, main as cli_main
from apertus_eval_prep.heldout import rank_instability_report


def _registry(tmp_path, cells, n=100):
    """Write a registry where `cells` maps (model, factor, level) -> accuracy."""
    path = tmp_path / "registry.jsonl"
    rows = []
    for (model, factor, level), acc in cells.items():
        rows.append({
            "run_id": f"{model}-{factor}-{level}",
            "model_id": model,
            "factor": factor,
            "factor_level": level,
            "status": "ok",
            "overall": {"accuracy": acc, "n": n},
        })
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def _three_models():
    """3 models x 4 configurations, with mA/mB swapping under 5-shot."""
    return {
        ("mA", "prompt_id", "base"): 0.70, ("mA", "prompt_id", "concise"): 0.62,
        ("mA", "prompt_id", "5shot"): 0.71, ("mA", "seed", "0"): 0.70,
        ("mB", "prompt_id", "base"): 0.66, ("mB", "prompt_id", "concise"): 0.67,
        ("mB", "prompt_id", "5shot"): 0.58, ("mB", "seed", "0"): 0.66,
        ("mC", "prompt_id", "base"): 0.55, ("mC", "prompt_id", "concise"): 0.50,
        ("mC", "prompt_id", "5shot"): 0.52, ("mC", "seed", "0"): 0.55,
    }


def test_heldout_writes_a_budget_curve(tmp_path):
    registry = _registry(tmp_path, _three_models())
    out = tmp_path / "out"
    assert cli_main([
        "heldout", "--registry", str(registry), "--out", str(out),
        "--budgets", "2,3", "--n-boot", "20", "--seed", "0",
    ]) == 0

    payload = json.loads((out / "heldout.json").read_text(encoding="utf-8"))
    assert payload["n_models"] == 3
    assert payload["n_configs"] == 4
    assert {r["budget"] for r in payload["budgets"]} == {2, 3}
    md = (out / "heldout.md").read_text(encoding="utf-8")
    assert "runs spent" in md and "held out" in md
    # A budget equal to the configuration count would leave nothing to predict.
    for b in payload["budgets"]:
        assert b["split"]["n_heldout"] >= 1


def test_heldout_is_deterministic_for_a_given_seed(tmp_path):
    registry = _registry(tmp_path, _three_models())
    first, second = tmp_path / "a", tmp_path / "b"
    for out in (first, second):
        assert cli_main([
            "heldout", "--registry", str(registry), "--out", str(out),
            "--budgets", "2,3", "--n-boot", "20", "--seed", "7",
        ]) == 0
    a = json.loads((first / "heldout.json").read_text(encoding="utf-8"))
    b = json.loads((second / "heldout.json").read_text(encoding="utf-8"))
    assert a["budgets"] == b["budgets"]


def test_heldout_refuses_a_budget_that_holds_out_nothing(tmp_path, capsys):
    registry = _registry(tmp_path, _three_models())
    assert cli_main([
        "heldout", "--registry", str(registry), "--out", str(tmp_path / "o"),
        "--budgets", "4",
    ]) == 1
    assert "budgets must satisfy" in capsys.readouterr().err


def test_heldout_records_the_leakage_guard(tmp_path):
    registry = _registry(tmp_path, _three_models())
    out = tmp_path / "o"
    assert cli_main([
        "heldout", "--registry", str(registry), "--out", str(out),
        "--budgets", "2", "--n-boot", "20",
    ]) == 0
    payload = json.loads((out / "heldout.json").read_text(encoding="utf-8"))
    for result in payload["budgets"]:
        assert "train" in result["provenance"]
        assert result["split"]["n_train"] + result["split"]["n_heldout"] == result["split"]["n_total"]


def test_missing_cells_stay_none_and_never_become_zero():
    """A configuration a model was never run under is unknown, not a failure.

    Imputing 0.0 would look like a total collapse and silently reorder the
    matrix, so the shared builder must leave it as None.
    """
    cells = _three_models()
    rows = [
        {"model_id": m, "factor": f, "factor_level": lv, "status": "ok",
         "overall": {"accuracy": acc, "n": 100}}
        for (m, f, lv), acc in cells.items()
    ]
    assert _registry_score_matrix(rows)["n_missing_cells"] == 0  # fixture is dense

    partial = [r for r in rows if not (r["model_id"] == "mC" and r["factor"] == "seed")]
    sparse = _registry_score_matrix(partial)
    assert sparse["n_missing_cells"] == 1
    assert None in [v for row in sparse["matrix"] for v in row]
    assert 0.0 not in [v for row in sparse["matrix"] for v in row]


def test_models_with_fewer_than_two_cells_are_excluded_not_zeroed():
    rows = [
        {"model_id": "mA", "factor": "prompt_id", "factor_level": "base",
         "status": "ok", "overall": {"accuracy": 0.7, "n": 10}},
        {"model_id": "mA", "factor": "prompt_id", "factor_level": "5shot",
         "status": "ok", "overall": {"accuracy": 0.8, "n": 10}},
        {"model_id": "mB", "factor": "prompt_id", "factor_level": "base",
         "status": "ok", "overall": {"accuracy": 0.6, "n": 10}},
        {"model_id": "mB", "factor": "prompt_id", "factor_level": "5shot",
         "status": "ok", "overall": {"accuracy": 0.5, "n": 10}},
        # One cell only: no within-model spread, so it cannot join the matrix.
        {"model_id": "mLonely", "factor": "prompt_id", "factor_level": "base",
         "status": "ok", "overall": {"accuracy": 0.9, "n": 10}},
    ]
    built = _registry_score_matrix(rows)
    assert built["models"] == ["mA", "mB"]
    assert built["excluded_models_lt2_cells"] == ["mLonely"]


def test_non_ok_and_empty_rows_are_ignored():
    rows = [
        {"model_id": "mA", "factor": "prompt_id", "factor_level": "base",
         "status": "ok", "overall": {"accuracy": 0.7, "n": 10}},
        {"model_id": "mA", "factor": "prompt_id", "factor_level": "5shot",
         "status": "failed", "overall": {"accuracy": 0.0, "n": 10}},
        {"model_id": "mA", "factor": "seed", "factor_level": "0",
         "status": "ok", "overall": {}},
    ]
    built = _registry_score_matrix(rows)
    assert "prompt_id=5shot" not in built["configs"]
    assert "seed=0" not in built["configs"]


def test_mixed_sample_sizes_are_reported_as_a_comparability_warning():
    rows = [
        {"run_id": "r1", "model_id": "mA", "factor": "prompt_id", "factor_level": "base",
         "status": "ok", "overall": {"accuracy": 0.7, "n": 100}},
        {"run_id": "r2", "model_id": "mA", "factor": "prompt_id", "factor_level": "5shot",
         "status": "ok", "overall": {"accuracy": 0.6, "n": 40}},
    ]
    assert [w["run_id"] for w in _registry_score_matrix(rows)["mixed_n_warnings"]] == ["r2"]


# --- rank instability -------------------------------------------------------
# The Qwen/Phi pair in the committed matrix is the case that motivates this:
# Phi wins 7 of 8 decidable configurations and Qwen wins exactly one, so an
# aggregate reliability metric can report perfect confidence in an ordering that
# a single reproducible configuration overturns.

KEYS = ["control=control", "prompt_id=5shot", "prompt_id=concise"]


def test_a_majority_pair_is_not_reversible():
    report = rank_instability_report(
        [[0.70, 0.71, 0.69], [0.60, 0.58, 0.61]], KEYS, ["A", "B"]
    )
    pair = report["pairs"][0]
    assert (pair["a_wins"], pair["b_wins"]) == (3, 0)
    assert pair["reversible"] is False
    assert report["n_reversible"] == 0


def test_one_reproducible_flip_makes_a_pair_reversible():
    # A wins control (0.70>0.65) and concise (0.69>0.61);
    # B wins 5-shot only (0.71>0.60).
    report = rank_instability_report(
        [[0.70, 0.60, 0.69], [0.65, 0.71, 0.61]], KEYS, ["A", "B"]
    )
    pair = report["pairs"][0]
    assert (pair["a_wins"], pair["b_wins"]) == (2, 1)
    assert pair["reversible"] is True
    # The minority side's configuration is the finding, so it must be named.
    assert pair["b_wins_on"] == ["prompt_id=5shot"]
    assert report["n_reversible"] == 1


def test_ties_are_neither_wins_nor_losses():
    # c1 is a tie (0.70 vs 0.70); c2 is an A win (0.70 vs 0.60).
    pair = rank_instability_report(
        [[0.70, 0.70], [0.70, 0.60]], ["c1", "c2"], ["A", "B"]
    )["pairs"][0]
    assert (pair["a_wins"], pair["b_wins"]) == (1, 0)
    assert pair["ties"] == ["c1"]
    assert pair["n_decidable"] == 1


def test_unmeasured_cells_are_listed_not_counted():
    pair = rank_instability_report(
        [[0.70, None], [0.60, 0.80]], ["c1", "c2"], ["A", "B"]
    )["pairs"][0]
    assert pair["unmeasured"] == ["c2"]
    assert pair["n_decidable"] == 1
    assert pair["a_wins"] == 1


def test_rank_instability_reaches_the_command_output(tmp_path):
    registry = _registry(tmp_path, _three_models())
    out = tmp_path / "o"
    assert cli_main([
        "heldout", "--registry", str(registry), "--out", str(out),
        "--budgets", "2", "--n-boot", "20",
    ]) == 0
    payload = json.loads((out / "heldout.json").read_text(encoding="utf-8"))
    assert "rank_instability" in payload
    assert len(payload["rank_instability"]["pairs"]) == 3  # 3 models -> 3 pairs
    assert "Rank instability" in (out / "heldout.md").read_text(encoding="utf-8")

