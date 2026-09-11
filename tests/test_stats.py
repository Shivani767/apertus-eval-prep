from apertus_eval_prep.stats import (
    benjamini_hochberg,
    bootstrap_paired_diff_ci,
    chi2_sf_1df,
    ci_width_curve,
    cis_overlap,
    holm_bonferroni,
    kendall_tau_b,
    mcnemar,
    pairwise_reversals,
    permutation_paired_test,
    rank_high_is_better,
    wilson_interval,
)
from apertus_eval_prep.scoring import is_correct, summarize_tasks


def test_wilson_bounds():
    lo, hi = wilson_interval(10, 10)
    assert lo is not None and hi is not None
    assert 0 <= lo < 1 <= hi or (lo < 1 and hi == 1)
    assert lo < 1.0
    none = wilson_interval(0, 0)
    assert none == (None, None)
    lo0, hi0 = wilson_interval(0, 20)
    assert lo0 == 0.0
    assert hi0 < 0.2


def test_mcnemar_identical_is_one():
    a = [True, True, False, False]
    out = mcnemar(a, list(a))
    assert out["p_value"] == 1.0
    assert out["disagreement_rate"] == 0.0
    flipped = [False, True, False, True]
    out2 = mcnemar(a, flipped)
    assert out2["a_correct_b_wrong"] == 1
    assert out2["a_wrong_b_correct"] == 1
    assert out2["p_value"] > 0.05


def test_kendall_and_reversals():
    assert kendall_tau_b([1, 2, 3], [1, 2, 3]) == 1.0
    assert kendall_tau_b([1, 2, 3], [3, 2, 1]) == -1.0
    ranks_a = rank_high_is_better([0.9, 0.5, 0.1])
    ranks_b = rank_high_is_better([0.1, 0.5, 0.9])
    assert ranks_a[0] == 1.0
    assert pairwise_reversals(ranks_a, ranks_b) == 3


def test_ci_overlap_and_ties():
    assert cis_overlap([0.1, 0.3], [0.2, 0.4]) is True
    assert cis_overlap([0.1, 0.2], [0.3, 0.4]) is False
    assert cis_overlap(None, [0.1, 0.2]) is None


def test_summarize_includes_wilson():
    rows = [{"task": "hellaswag", "correct": True}] * 8 + [{"task": "hellaswag", "correct": False}] * 2
    block = summarize_tasks(rows)["hellaswag"]
    assert block["accuracy"] == 0.8
    assert block["accuracy_ci95"][0] < 0.8 < block["accuracy_ci95"][1]


def test_hellaswag_and_mgsm_scoring():
    assert is_correct("hellaswag", "The best ending is C.", "C")
    assert is_correct("mgsm", "Antwort: 12", "12")
    assert not is_correct("hellaswag", "maybe", "A")


def test_chi2_sf_sane():
    assert chi2_sf_1df(0) == 1.0
    assert 0.0 < chi2_sf_1df(3.84) < 0.06


def test_ci_width_curve_shrinks_and_n4_is_wide():
    curve = ci_width_curve([True, False, True, False])
    assert curve[0]["n"] == 1
    assert curve[-1]["n"] == 4
    assert curve[-1]["correct"] == 2
    assert curve[-1]["width"] > 0.6
    wider_early = curve[0]["width"]
    assert wider_early >= curve[-1]["width"]
    long = ci_width_curve([True] * 20 + [False] * 8)
    assert long[-1]["width"] < curve[-1]["width"]


def _ids(n, prefix="it"):
    return [f"{prefix}/{i}" for i in range(n)]


def _det(i, mod):
    """Deterministic pseudo-random bit for item id (no salted hash())."""
    k = int(i.split("/")[-1])
    return (k * 2654435761 % mod)


def test_bootstrap_paired_diff_ci_synthetic():
    ids = _ids(200)
    a = {i: _det(i, 10) < 5 for i in ids}
    b = {i: a[i] or (_det(i, 7) == 0) for i in ids}  # B >= A per item
    out = bootstrap_paired_diff_ci(a, b, n_boot=500, seed=1)
    assert out["n_paired"] == 200 and out["n_dropped"] == 0
    assert out["delta_mean"] > 0
    assert out["lo"] >= 0 and out["hi"] > out["lo"]
    out2 = bootstrap_paired_diff_ci(a, b, n_boot=500, seed=1)
    assert (out2["lo"], out2["hi"]) == (out["lo"], out["hi"])  # deterministic
    b_partial = dict(list(b.items())[:150])
    out3 = bootstrap_paired_diff_ci(a, b_partial, n_boot=100, seed=2)
    assert out3["n_dropped"] == 50 and out3["n_paired"] == 150
    empty = bootstrap_paired_diff_ci({}, {"x": True})
    assert empty["lo"] is None and empty["n_paired"] == 0


def test_permutation_paired_test_synthetic():
    ids = _ids(120)
    a = {i: _det(i, 10) < 5 for i in ids}
    b = {i: a[i] or (_det(i, 6) == 0) for i in ids}
    res = permutation_paired_test(a, b, n_perm=800, seed=3)
    assert res["method"] == "sign-flip"
    assert res["delta_obs"] > 0
    assert 0.0 < res["p_value"] <= 1.0
    assert res["p_value"] <= 0.1  # clear synthetic effect is significant
    same = permutation_paired_test(a, dict(a), n_perm=200, seed=4)
    assert same["p_value"] == 1.0 and same["delta_obs"] == 0.0
    res2 = permutation_paired_test(a, b, n_perm=800, seed=3)
    assert res2["p_value"] == res["p_value"]  # deterministic seed


def test_multiple_comparison_corrections():
    ps = [0.001, 0.008, 0.039, 0.041, 0.2, 0.8]
    holm = holm_bonferroni(ps)
    bh = benjamini_hochberg(ps)
    assert holm[0] <= holm[1] <= holm[2]  # order-preserving monotonicity
    assert bh[0] <= bh[1] <= bh[2]
    assert all(b <= h for b, h in zip(bh, holm))  # FDR <= FWER adjustment
    assert holm[0] == 0.006  # 6 * 0.001
    assert holm[1] == 0.04   # 5 * 0.008
    assert bh[0] == 0.006    # 6 * 0.001 / 1
    assert bh[1] == 0.024    # 6 * 0.008 / 2
    # Holm's largest is (m - rank) * p = 1 * 0.8 = 0.8 (not clipped here)
    assert holm[-1] == 0.8
    # clipping to 1 happens when the step-down running value exceeds 1
    assert holm_bonferroni([0.6, 0.6]) == [1.0, 1.0]
    assert max(benjamini_hochberg([0.4, 0.4])) == 1.0
    with pytest.raises(ValueError):
        holm_bonferroni([0.5, 1.5])
    with pytest.raises(ValueError):
        benjamini_hochberg([-0.1])
    assert benjamini_hochberg([]) == []
    assert holm_bonferroni([0.5]) == [0.5]
