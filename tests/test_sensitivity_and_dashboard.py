"""Evaluation sensitivity and dashboard sections: report before combining.

Two properties are defended. First, ESI is dimensionless, so it is only computed
against an explicitly declared scale -- inventing a convenient default would
produce a confident number whose unit nobody agreed on. Second, a dashboard
section with no committed artifact must say "not generated" rather than render
zeros, because a dashboard that cannot distinguish "not measured" from
"measured zero" is actively misleading.
"""

from __future__ import annotations

import json

import pytest

from apertus_eval_prep.dashboard_sections import SECTION_ARTIFACTS, build_analysis_sections
from apertus_eval_prep.sensitivity import factor_sensitivity_index, wilson_uncertainty_scale


def _rows():
    rows = []
    for index, (prompt, backend) in enumerate([
        ("baseline", "hf"), ("fewshot", "hf"), ("baseline", "vllm"), ("fewshot", "vllm"),
    ]):
        for offset in (0.0, 0.005, 0.01):
            rows.append({"prompt": prompt, "backend": backend,
                         "score": 0.50 + 0.02 * index + offset})
    return rows


class TestFactorSensitivity:
    def test_absolute_and_relative_deltas_are_reported(self):
        result = factor_sensitivity_index(_rows(), ["prompt", "backend"])
        by_factor = {f["factor"]: f for f in result["factors"]}
        # This fixture moves prompt and backend together, so each marginal
        # effect is half the total range: a sensitivity index is a *marginal*
        # statistic, and separating the two needs a crossed design.
        assert by_factor["prompt"]["absolute_delta"] == pytest.approx(0.02)
        assert by_factor["backend"]["absolute_delta"] == pytest.approx(0.04)
        assert by_factor["backend"]["relative_delta"] > by_factor["prompt"]["relative_delta"]

    def test_effect_size_and_interval_are_present(self):
        result = factor_sensitivity_index(_rows(), ["prompt"], n_boot=200)
        factor = result["factors"][0]
        assert factor["standardized_effect_cohens_h"] is not None
        low, high = factor["confidence_interval_95"]
        assert low <= factor["absolute_delta"] <= high

    def test_esi_requires_a_declared_scale(self):
        result = factor_sensitivity_index(_rows(), ["prompt"], uncertainty_scale=None)
        factor = result["factors"][0]
        assert factor["esi"] is None
        assert "no uncertainty scale" in factor["esi_reason"]
        # The underlying measurements are still there.
        assert factor["absolute_delta"] is not None

    def test_esi_is_the_delta_over_the_declared_scale(self):
        scale = wilson_uncertainty_scale(0.55, 100)
        result = factor_sensitivity_index(_rows(), ["prompt"], uncertainty_scale=scale)
        factor = result["factors"][0]
        assert factor["esi"] == pytest.approx(factor["absolute_delta"] / scale, rel=1e-5)
        assert factor["esi_scale"] == scale

    def test_a_zero_scale_is_refused_rather_than_dividing_by_zero(self):
        result = factor_sensitivity_index(_rows(), ["prompt"], uncertainty_scale=0.0)
        assert result["factors"][0]["esi"] is None

    def test_most_and_least_sensitive_factors_are_identified(self):
        result = factor_sensitivity_index(_rows(), ["prompt", "backend"])
        assert result["most_sensitive_factor"] == "backend"
        assert result["least_sensitive_factor"] == "prompt"

    def test_crossed_design_separates_independent_effects(self):
        # prompt and backend now vary independently, so each marginal effect is
        # its own effect rather than half of a confounded range.
        rows = []
        for prompt, prompt_shift in (("baseline", 0.0), ("fewshot", 0.02)):
            for backend, backend_shift in (("hf", 0.0), ("vllm", 0.06)):
                for offset in (0.0, 0.005, 0.01):
                    rows.append({"prompt": prompt, "backend": backend,
                                 "score": 0.50 + prompt_shift + backend_shift + offset})
        result = factor_sensitivity_index(rows, ["prompt", "backend"])
        by_factor = {f["factor"]: f for f in result["factors"]}
        assert by_factor["prompt"]["absolute_delta"] == pytest.approx(0.02)
        assert by_factor["backend"]["absolute_delta"] == pytest.approx(0.06)
        assert result["most_sensitive_factor"] == "backend"

    def test_unknown_factor_is_unavailable_not_zero(self):
        result = factor_sensitivity_index(_rows(), ["nope"])
        assert result["status"] == "insufficient_design"
        entry = result["factors"][0]
        assert entry["status"] == "UNAVAILABLE"
        assert entry["absolute_delta"] is None
        assert entry["esi"] is None

    def test_single_level_factor_has_no_spread(self):
        rows = [{"prompt": "only", "score": 0.5}, {"prompt": "only", "score": 0.6}]
        result = factor_sensitivity_index(rows, ["prompt"])
        assert result["factors"][0]["n_levels"] == 1
        assert result["factors"][0]["absolute_delta"] == 0.0

    def test_definitions_and_assumptions_are_in_the_artifact(self):
        result = factor_sensitivity_index(_rows(), ["prompt"])
        assert "esi" in result["definitions"]
        assert result["assumptions"]
        assert any("not a quality score" in limit for limit in result["limits"])

    def test_no_composite_across_factors_is_produced(self):
        result = factor_sensitivity_index(_rows(), ["prompt", "backend"])
        assert "composite" not in result
        assert "overall_esi" not in result

    def test_evidence_and_disclaimer_are_attached(self):
        result = factor_sensitivity_index(_rows(), ["prompt"], evidence={"mode": "MOCK"})
        assert result["evidence"]["mode"] == "MOCK"
        assert "not a model quality score" in result["disclaimer"]

    def test_deterministic_and_json_safe(self):
        first = factor_sensitivity_index(_rows(), ["prompt"], n_boot=100, seed=4)
        second = factor_sensitivity_index(_rows(), ["prompt"], n_boot=100, seed=4)
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


class TestDashboardSections:
    def test_every_specified_section_has_an_artifact_mapping(self):
        assert set(SECTION_ARTIFACTS) == {
            "evaluation_sensitivity", "ranking_stability", "decision_stability",
            "interaction_analysis", "agent_reliability", "scenario_coverage",
        }

    def test_missing_artifacts_report_not_generated_never_zero(self, tmp_path):
        sections = build_analysis_sections(tmp_path)
        for key in SECTION_ARTIFACTS:
            section = sections[key]
            assert section["status"] == "not_generated"
            assert section["expected_artifact"]
            assert "zero-filled" in section["note"]
            # No value-bearing container is invented for a missing artifact.
            assert "factors" not in section
            assert "metrics" not in section

    def test_a_present_artifact_is_projected_not_recomputed(self, tmp_path):
        target = tmp_path / "reports" / "ranking_stability"
        target.mkdir(parents=True)
        (target / "ranking_stability.json").write_text(json.dumps({
            "metric": "ranking_stability", "k": 2, "mean_kendall_tau": 0.5,
            "top_1_stability": 0.0, "top_k_stability": 1.0,
            "rank_reversal_rate": 0.5, "mean_pairwise_inversion_rate": 0.25,
            "valid_perturbations": 2, "incomparable_perturbations": 1,
            "composite_score": None, "composite_rationale": "kept separate",
            "disclaimer": "diagnostic", "evidence": {"mode": "MOCK"},
        }), encoding="utf-8")
        section = build_analysis_sections(tmp_path)["ranking_stability"]
        assert section["status"] == "ok"
        assert section["mean_kendall_tau"] == 0.5
        assert section["top_1_stability"] == 0.0
        assert section["top_k_stability"] == 1.0
        assert section["composite_score"] is None
        assert "committed analysis artifact" in section["provenance"]

    def test_corrupt_artifact_is_reported_not_silently_zeroed(self, tmp_path):
        target = tmp_path / "reports" / "decision_stability"
        target.mkdir(parents=True)
        (target / "decision_stability.json").write_text("{not json", encoding="utf-8")
        section = build_analysis_sections(tmp_path)["decision_stability"]
        assert section["status"] == "not_generated"
        assert "unreadable" in section["source"]
