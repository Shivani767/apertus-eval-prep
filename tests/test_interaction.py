"""Tests for the interaction-study subsystem (research Phase 2).

Synthetic study dicts only; no model runs. Verifies design determinism,
balance properties, provenance keys, and compatibility with the existing
sweep cell structure (RunConfig-compatible keys).
"""

import pytest

from apertus_eval_prep.interaction import (
    DESIGNS,
    INTERACTION_PAIRS,
    all_level_combos,
    balanced_select,
    expand_interaction,
    interaction_design,
    interaction_id,
    interaction_study,
    levels_for,
    summarized_study,
)

STUDY = {
    "study": "interaction_test",
    "experiment_id": "ix_test",
    "control": {
        "backend": "hf",
        "quantization": "none",
        "seed": 0,
        "temperature": 0.0,
        "top_p": 1.0,
        "prompt_id": "p0",
    },
    "models": ["m-a", "m-b"],
    "factors": {
        "prompt_id": ["p0", "p1"],
        "backend": ["hf", "vllm"],
        "quantization": ["none", "int8"],
    },
    "sampled": {"temperature": 0.7, "top_p": 0.95},
}


# ---------------------------------------------------------------------------
# factor definitions / levels
# ---------------------------------------------------------------------------


def test_levels_resolved_from_study():
    assert levels_for(STUDY, "prompt") == ["p0", "p1"]
    assert levels_for(STUDY, "backend") == ["hf", "vllm"]
    assert levels_for(STUDY, "quantization") == ["none", "int8"]
    assert levels_for(STUDY, "decoding") == ["greedy", "sampled"]


def test_decoding_levels_require_sampled_block():
    study = {"factors": {"prompt_id": ["p0", "p1"]}}
    with pytest.raises(ValueError, match="sampled"):
        levels_for(study, "decoding")


def test_unknown_factor_raises():
    with pytest.raises(KeyError):
        levels_for(STUDY, "quantizashun")


# ---------------------------------------------------------------------------
# full (Cartesian) design
# ---------------------------------------------------------------------------


def test_full_design_is_cartesian():
    combos = all_level_combos(STUDY, "prompt×backend")
    assert len(combos) == 4
    assert {"prompt": "p0", "backend": "hf"} in combos
    assert {"prompt": "p1", "backend": "vllm"} in combos


def test_full_design_within_budget_returns_everything():
    info = interaction_design(STUDY, "prompt×backend", design="full", max_cells=4)
    assert info["selected_size"] == info["full_size"] == 4
    assert len(info["combos"]) == 4


def test_full_design_raises_when_exceeds_budget():
    with pytest.raises(ValueError, match="balanced"):
        interaction_design(STUDY, "prompt×backend", design="full", max_cells=3)


def test_all_four_pairs_supported():
    for pair in INTERACTION_PAIRS:
        info = interaction_design(STUDY, pair, design="full")
        assert info["selected_size"] == info["full_size"]


def test_unknown_pair_and_design_raise():
    with pytest.raises(ValueError, match="interaction pair"):
        interaction_design(STUDY, "prompt×seed")
    with pytest.raises(ValueError, match="design"):
        interaction_design(STUDY, "prompt×backend", design="orthogonal")


# ---------------------------------------------------------------------------
# balanced (fractional) design
# ---------------------------------------------------------------------------


def test_balanced_respects_budget_and_marginal_balance():
    combos = all_level_combos(STUDY, "prompt×quantization")  # 2 x 2 = 4
    picked = balanced_select(combos, 2, seed=0)
    assert len(picked) == 2
    # marginal balance: k=2 over 2 levels per axis -> each level exactly once
    for axis in ("prompt", "quantization"):
        counts = {}
        for c in picked:
            counts[c[axis]] = counts.get(c[axis], 0) + 1
        assert set(counts.values()) == {1}


def test_balanced_larger_grid_is_approximately_balanced():
    study = dict(STUDY)
    study["factors"] = {
        "prompt_id": ["p0", "p1", "p2"],
        "backend": ["hf", "vllm", "mock"],
    }
    combos = all_level_combos(study, "prompt×backend")  # 9
    picked = balanced_select(combos, 6, seed=1)
    assert len(picked) == 6
    for axis in ("prompt", "backend"):
        counts = {}
        for c in picked:
            counts[c[axis]] = counts.get(c[axis], 0) + 1
        assert max(counts.values()) - min(counts.values()) <= 1


def test_balanced_is_deterministic_per_seed():
    combos = all_level_combos(STUDY, "prompt×backend")
    a = balanced_select(combos, 3, seed=42)
    b = balanced_select(combos, 3, seed=42)
    assert a == b


def test_balanced_k_zero_raises_and_k_full_returns_all():
    combos = all_level_combos(STUDY, "prompt×backend")
    with pytest.raises(ValueError, match="k >= 1"):
        balanced_select(combos, 0)
    assert balanced_select(combos, 99) == combos


# ---------------------------------------------------------------------------
# experiment ids + provenance
# ---------------------------------------------------------------------------


def test_interaction_id_stable_and_descriptive():
    info = interaction_design(STUDY, "prompt×backend", design="balanced",
                              seed=3, max_cells=3)
    id1 = interaction_id(info)
    id2 = interaction_id(interaction_design(STUDY, "prompt×backend", design="balanced",
                                            seed=3, max_cells=3))
    assert id1 == id2
    assert "prompt×backend" in id1 and "3-of-4" in id1 and "seed3" in id1


def test_cells_carry_provenance_and_run_keys():
    cells = expand_interaction(STUDY, "prompt×quantization", design="full",
                               include_control=False)
    assert len(cells) == 4 * 2  # 4 combos x 2 models
    for cell in cells:
        assert cell["design"] == "full"
        assert cell["design_axes"] == ["prompt", "quantization"]
        assert cell["interaction_id"]
        assert cell["factor"] == "prompt×quantization"
        # RunConfig-compatible keys inherited from _base_cell
        for key in ("model_id", "prompt_id", "backend", "quantization",
                    "temperature", "seed", "data_path"):
            assert key in cell


def test_control_cells_included_when_requested():
    cells = expand_interaction(STUDY, "prompt×quantization", include_control=True)
    controls = [c for c in cells if c["factor"] == "control"]
    assert len(controls) == len(STUDY["models"])


def test_decoding_level_applied_to_cell():
    cells = expand_interaction(STUDY, "prompt×decoding", design="full",
                               include_control=False)
    temps = {c["temperature"] for c in cells}
    assert temps == {0.0, 0.7}


# ---------------------------------------------------------------------------
# study-level assembly
# ---------------------------------------------------------------------------


def test_interaction_study_assembles_all_pairs():
    out = interaction_study(STUDY, design="full", include_control=False)
    assert out["experiment_type"] == "interaction_study"
    assert set(out["studies"]) == set(INTERACTION_PAIRS)
    assert out["n_cells"] == len(INTERACTION_PAIRS) * 4 * 2
    assert summarized_study(out)["experiment_type"] == "interaction_study"


def test_interaction_study_deterministic():
    a = interaction_study(STUDY, design="balanced", seed=7,
                          max_cells_per_pair=2, include_control=True)
    b = interaction_study(STUDY, design="balanced", seed=7,
                          max_cells_per_pair=2, include_control=True)
    assert a["cells"] == b["cells"]
    assert a["studies"] == b["studies"]


def test_designs_constant_shape():
    assert set(DESIGNS) == {"full", "balanced"}
