import json
from pathlib import Path

from apertus_eval_prep.config import load_config
from apertus_eval_prep.prompting import load_prompt_spec, wrap_item
from apertus_eval_prep.prompts import EvalItem, load_items
from apertus_eval_prep.registry import config_hash
from apertus_eval_prep.sweep import expand_ofat, load_study


ROOT = Path(__file__).resolve().parents[1]


def test_old_smoke_yaml_still_loads():
    cfg = load_config(ROOT / "configs" / "smoke.yaml")
    assert cfg.backend == "hf"
    assert cfg.quantization == "none"
    assert cfg.temperature == 0.0
    assert cfg.prompt_id is None


def test_quant_and_prompt_validation():
    cfg = load_config(ROOT / "configs" / "default.yaml", {"quantization": "int4", "prompt_id": "concise"})
    assert cfg.quantization == "int4"
    assert cfg.prompt_id == "concise"


def test_ofat_expansion_count():
    study = load_study(ROOT / "tests" / "fixtures" / "study.yaml")
    cells = expand_ofat(study)
    assert len(cells) == 12
    factors = {(c["factor"], c["factor_level"]) for c in cells}
    assert ("control", "control") in factors
    assert ("prompt_id", "concise") in factors
    assert ("backend", "vllm") in factors
    assert ("quantization", "int4") in factors
    assert ("sampled", "t0.7_seed0") in factors
    t4 = expand_ofat(study, profile="t4")
    assert len(t4) == 11
    assert not any(c["model_id"] == "org/B" and c["backend"] == "vllm" for c in t4)


def test_config_hash_stable():
    a = {"model_id": "m", "backend": "hf", "seed": 0, "tasks": ["arc_easy"]}
    b = {"seed": 0, "backend": "hf", "model_id": "m", "tasks": ["arc_easy"]}
    assert config_hash(a) == config_hash(b)
    c = dict(a)
    c["seed"] = 1
    assert config_hash(a) != config_hash(c)


def test_prompt_wrap_adds_instruction_and_fewshot():
    spec = load_prompt_spec(ROOT, "5shot")
    item = EvalItem(id="x", task="arc_easy", language="en", gold="B", prompt="Q?\nA) 1\nB) 2\nC) 3\nD) 4")
    shots = {
        "arc_easy": [
            EvalItem(id=f"s{i}", task="arc_easy", language="en", gold="A", prompt=f"ex{i}")
            for i in range(5)
        ]
    }
    text = wrap_item(item, spec, shots)
    assert text.count("Answer: A") == 5
    assert "Reply with the letter" in text
    assert text.endswith("Reply with the letter of the correct answer (A, B, C, or D).")


def test_no_wrap_when_prompt_id_unset():
    item = EvalItem(id="x", task="arc_easy", language="en", gold="B", prompt="already complete")
    assert wrap_item(item, None, None) == "already complete"


def test_invalid_quantization():
    import pytest
    from apertus_eval_prep.config import load_config

    with pytest.raises(ValueError, match="quantization"):
        load_config(ROOT / "configs" / "smoke.yaml", {"quantization": "awq"})


def test_stability_yaml_t4_skips_7b_fp16():
    study = load_study(ROOT / "configs" / "experiments" / "stability.yaml")
    all_cells = expand_ofat(study)
    t4 = expand_ofat(study, profile="t4")
    seven = "Qwen/Qwen2.5-7B-Instruct"
    assert any(c["model_id"] == seven and c["quantization"] == "none" for c in all_cells)
    assert not any(c["model_id"] == seven and c["quantization"] == "none" for c in t4)
    assert any(c["model_id"] == seven and c["quantization"] == "int4" for c in t4)


def test_only_model_filter():
    study = load_study(ROOT / "configs" / "experiments" / "stability.yaml")
    t4 = expand_ofat(study, profile="t4")
    one = "HuggingFaceTB/SmolLM2-1.7B-Instruct"
    filtered = [c for c in t4 if c["model_id"] == one]
    assert filtered
    assert all(c["model_id"] == one for c in filtered)
    assert len(filtered) < len(t4)


def test_only_factor_control_is_one_cell_per_t4_model():
    study = load_study(ROOT / "configs" / "experiments" / "stability.yaml")
    t4 = expand_ofat(study, profile="t4")
    controls = [c for c in t4 if c.get("factor") == "control"]
    models = {c["model_id"] for c in controls}
    assert models == {
        "HuggingFaceTB/SmolLM2-1.7B-Instruct",
        "Qwen/Qwen2.5-3B-Instruct",
        "microsoft/Phi-3.5-mini-instruct",
    }
    assert len(controls) == 3


def test_fixture_items_parse():
    items = load_items(ROOT / "tests" / "fixtures" / "official_tiny.jsonl", ["arc_easy", "gsm8k"], None)
    assert len(items) == 4
    ids = [row["id"] for row in (json.loads(l) for l in (ROOT / "tests/fixtures/official_tiny.jsonl").read_text().splitlines() if l.strip())]
    assert len(ids) == len(set(ids))
