import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "data" / "official"


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_official_eval_set_is_frozen_and_unique():
    rows = _load(OFFICIAL / "eval_set.jsonl")
    assert len(rows) == 800
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids))
    counts = Counter(r["task"] for r in rows)
    assert counts == {"arc_easy": 200, "gsm8k": 200, "hellaswag": 200, "mgsm": 200}
    mgsm = [r for r in rows if r["task"] == "mgsm"]
    langs = Counter(r["language"] for r in mgsm)
    assert langs["en"] == 67 and langs["de"] == 67 and langs["fr"] == 66
    for row in rows:
        assert row["gold"]
        assert row["prompt"]
        if row["task"] in {"arc_easy", "hellaswag"}:
            assert row["gold"] in "ABCD"


def test_fewshot_does_not_overlap_eval():
    eval_ids = {r["id"] for r in _load(OFFICIAL / "eval_set.jsonl")}
    few = _load(OFFICIAL / "fewshot.jsonl")
    assert len(few) == 20
    few_ids = {r["id"] for r in few}
    assert not (eval_ids & few_ids)
    assert Counter(r["task"] for r in few) == {
        "arc_easy": 5,
        "gsm8k": 5,
        "hellaswag": 5,
        "mgsm": 5,
    }


def test_sources_records_hub_sha():
    text = (OFFICIAL / "SOURCES.md").read_text(encoding="utf-8")
    assert "allenai/ai2_arc" in text
    assert "openai/gsm8k" in text
    assert "Rowan/hellaswag" in text
    assert "juletxara/mgsm" in text
    assert "generative exact-match" in text
