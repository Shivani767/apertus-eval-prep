from apertus_eval_prep.stats import (
    chi2_sf_1df,
    cis_overlap,
    kendall_tau_b,
    mcnemar,
    pairwise_reversals,
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
