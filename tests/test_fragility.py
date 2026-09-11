"""Tests for Phase 4 (fragility) + Phase 6 (variance). Synthetic only."""

from apertus_eval_prep import fragility, variance


def test_fragility_components():
    s = fragility.score_sensitivity([0.5, 0.6, 0.7])
    assert abs(s["range"] - 0.2) < 1e-9 and s["n"] == 3
    r = fragility.rank_sensitivity([0.9, 0.6, 0.3], [0.3, 0.6, 0.9])
    assert r["kendall_tau"] == -1.0 and r["reversals"] == 3
    r1 = fragility.rank_sensitivity([0.9], [0.8])
    assert r1["kendall_tau"] is None  # <2 models: undefined, not 0
    t = fragility.tie_fragility(["a", "b"], [0.67, 0.64], [[0.63, 0.70], [0.61, 0.67]])
    assert t == {"n_pairs": 1, "n_ties": 1, "tie_fraction": 1.0}
    pf = fragility.per_factor_sensitivity({"prompt": {"x": [0.5], "y": [0.7]}})
    assert abs(pf["prompt"]["max_abs_delta"] - 0.2) < 1e-9
    sp = fragility.sampling_spread([0.36, 0.3675, 0.39])
    assert sp["n"] == 3 and sp["range"] > 0
    summ = fragility.model_rank_summary(["a", "b"], [[0.9, 0.8], [0.6, 0.7]])
    assert summ[0]["model_id"] == "a" and summ[0]["p_rank_1"] == 1.0


def test_provisional_efi_formula_weights_ablation():
    import pytest

    full = fragility.evaluation_fragility_index(
        score_range=0.17, kendall_tau=0.3333, tie_fraction=1 / 3, sampling_cv=0.05)
    assert full["provisional"] is True
    assert 0.0 <= full["efi"] <= 1.0
    assert full["missing"] == [] and full["tau_undefined"] is False
    # tau None -> flagged uncertain 0.5 rank term, not hidden
    u = fragility.evaluation_fragility_index(
        score_range=0.1, kendall_tau=None, tie_fraction=0.0, sampling_cv=0.0)
    assert u["tau_undefined"] is True and u["terms"]["rank_instability"] == 0.5
    # missing terms renormalize + listed
    m = fragility.evaluation_fragility_index(
        score_range=None, kendall_tau=1.0, tie_fraction=None, sampling_cv=None)
    assert m["missing"] == ["score_range", "tie_fraction", "sampling_cv"]
    assert m["efi"] == 0.0  # only perfect-rank term remains
    with pytest.raises(ValueError, match="weights"):
        fragility.evaluation_fragility_index(
            score_range=0.1, kendall_tau=1.0, tie_fraction=0.0,
            sampling_cv=0.0, weights={})
    abl = fragility.efi_ablation(
        score_range=0.17, kendall_tau=0.3333, tie_fraction=1 / 3, sampling_cv=0.05)
    assert set(abl) == {"full", "drop_score_range", "drop_rank_instability",
                        "drop_tie_fraction", "drop_sampling_cv"}
    assert all("delta_vs_full" in v for k, v in abl.items() if k != "full")


def test_variance_descriptive_and_ofat_limits():
    rows = [{"prompt": "a", "score": 0.5}, {"prompt": "a", "score": 0.5},
            {"prompt": "b", "score": 0.7}, {"prompt": "b", "score": 0.7}]
    e = variance.eta_squared_one_way(rows, "prompt")
    assert 0.0 <= e["eta_squared"] <= 1.0 and e["n"] == 4
    assert variance.eta_squared_one_way([{"prompt": "a", "score": 0.5}], "prompt")["eta_squared"] is None
    d = variance.decompose_variance(rows, ["prompt", "backend"])
    assert d["by_factor"][0]["factor"] == "prompt"
    assert "OFAT" in d["assumptions"]
    # OFAT (no crossed cells) must NOT produce an interaction estimate
    ofat = [{"prompt": "x", "backend": "hf", "score": 0.5},
            {"prompt": "y", "backend": "hf", "score": 0.6}]
    s = variance.interaction_screen(ofat, "prompt", "backend")
    assert s["status"] == "UNAVAILABLE" and s["crossed_design"] is False
    crossed = [{"prompt": p, "backend": b, "score": v}
               for (p, b, v) in [("x", "hf", 0.5), ("x", "v", 0.6),
                                 ("y", "hf", 0.7), ("y", "v", 0.65)]]
    s2 = variance.interaction_screen(crossed, "prompt", "backend")
    assert s2["status"] == "MEASURED" and len(s2["combo_means"]) == 4
