"""Tests for Phase 10: evaluation cost tracking. Synthetic data + committed run files."""

import glob

import pytest

from apertus_eval_prep.cost import (
    CostRecord,
    budget_curve,
    cost_from_run_file,
    extract_cost,
    summarize_costs,
)
from apertus_eval_prep.result_schema import DERIVED, MEASURED, UNAVAILABLE


def _synthetic_run(**latency_overrides):
    latency = {
        "n": 800,
        "ttft_ms_mean": 400.24,
        "ttft_ms_p50": 400.0,
        "ttft_ms_p95": 1207.63,
        "e2e_ms_mean": 9116.87,
        "e2e_ms_p95": 12701.62,
        "tokens_per_sec_mean": 19.931,
    }
    latency.update(latency_overrides)
    return {"run_id": "synthetic-run", "latency": latency}


def test_extract_measured_and_derived():
    rec = extract_cost(_synthetic_run(), run_id="r1")
    assert rec.run_id == "r1"
    assert rec.n_calls == 800
    assert rec.quality["n_calls"] == MEASURED
    for f in ("ttft_ms_mean", "e2e_ms_mean", "tokens_per_sec_mean"):
        assert rec.quality[f] == MEASURED
    assert rec.e2e_ms_mean == pytest.approx(9116.87)
    # DERIVED estimate: e2e_ms_mean * n / 1000
    assert rec.est_total_s == pytest.approx(9116.87 * 800 / 1000)
    assert rec.quality["est_total_s"] == DERIVED


def test_unavailable_never_zero_filled():
    # 0.0, None, negative, string, missing key -> all UNAVAILABLE, raw preserved
    rec = extract_cost(_synthetic_run(
        e2e_ms_mean=0.0, ttft_ms_mean=None,
        tokens_per_sec_mean=-5, n=0,
    ))
    assert rec.n_calls is None
    assert rec.quality["n_calls"] == UNAVAILABLE
    for f in ("ttft_ms_mean", "e2e_ms_mean", "tokens_per_sec_mean"):
        assert getattr(rec, f) is None
        assert rec.quality[f] == UNAVAILABLE
    assert rec.est_total_s is None
    assert rec.quality["est_total_s"] == UNAVAILABLE
    assert rec.raw["e2e_ms_mean"] == 0.0  # raw value preserved, not rewritten


def test_real_committed_runs_match_expected_quality():
    # Committed evidence: HF control run recorded real timings, vLLM cell
    # recorded 0.0 placeholders -> cost model must classify them accordingly.
    hf = glob.glob("results/runs/Phi-3.5-mini-instruct_control_control_*.json")
    vllm = glob.glob("results/runs/Phi-3.5-mini-instruct_backend_vllm_*.json")
    if not (hf and vllm):
        pytest.skip("committed run artifacts not present")
    rec_hf = cost_from_run_file(hf[0])
    assert rec_hf.quality["e2e_ms_mean"] == MEASURED
    assert rec_hf.n_calls == 800
    rec_vllm = cost_from_run_file(vllm[0])
    assert rec_vllm.quality["e2e_ms_mean"] == UNAVAILABLE  # 0.0 placeholder
    assert rec_vllm.raw["e2e_ms_mean"] == 0.0
    assert rec_vllm.est_total_s is None


def test_summarize_counts_missing_without_zero_fill():
    recs = [
        extract_cost(_synthetic_run()),
        extract_cost(_synthetic_run(e2e_ms_mean=0.0, ttft_ms_mean=None,
                                    tokens_per_sec_mean=None, n=None)),
    ]
    s = summarize_costs(recs)
    assert s["n_runs"] == 2
    assert s["fields"]["n_calls"]["n_available"] == 1
    assert s["fields"]["ttft_ms_mean"]["n_available"] == 1
    assert s["fields"]["e2e_ms_mean"]["n_available"] == 1
    assert s["fields"]["tokens_per_sec_mean"]["n_available"] == 1
    assert s["fields"]["e2e_ms_mean"]["measured_fraction"] == 0.5
    assert s["est_total_s"]["n"] == 1
    assert s["est_total_s"]["sum"] == pytest.approx(9116.87 * 800 / 1000)


def test_budget_curve_validates_and_sorts():
    pts = budget_curve([(10.0, 0.5), (2.0, 0.4), (5.0, 0.6)])
    assert [p["cost"] for p in pts] == [2.0, 5.0, 10.0]
    assert pts[0]["confidence"] == pytest.approx(0.4)
    assert budget_curve([]) == []
    with pytest.raises(ValueError, match="cost"):
        budget_curve([(-1.0, 0.5)])
    with pytest.raises(ValueError, match="confidence"):
        budget_curve([(1.0, 1.5)])
    with pytest.raises(ValueError, match="confidence"):
        budget_curve([(1.0, -0.1)])


def test_cost_record_to_dict_roundtrip():
    rec = extract_cost(_synthetic_run())
    d = rec.to_dict()
    assert d["run_id"] == "synthetic-run"
    assert d["quality"]["est_total_s"] == DERIVED
    # default record: everything unavailable
    empty = CostRecord().to_dict()
    assert empty["n_calls"] is None and empty["quality"] == {}
