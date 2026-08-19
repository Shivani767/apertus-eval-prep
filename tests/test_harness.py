import json
from pathlib import Path

from apertus_eval_prep.compare import compare_runs, to_markdown
from apertus_eval_prep.config import load_config
from apertus_eval_prep.prompts import load_items
from apertus_eval_prep.templates import MISMATCHED_LLAMA3, render_prompt


def test_eval_set_parses():
    root = Path(__file__).resolve().parents[1]
    lines = (root / "data" / "eval_set.jsonl").read_text(encoding="utf-8").splitlines()
    items = [json.loads(line) for line in lines if line.strip()]
    assert len(items) == 28
    tasks = {row["task"] for row in items}
    assert tasks == {"arc_easy", "gsm8k", "multilingual", "template_canary"}
    ids = [row["id"] for row in items]
    assert len(ids) == len(set(ids))


def test_load_config_and_items(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "configs" / "smoke.yaml")
    assert cfg.backend == "hf"
    assert cfg.chat_template == "tokenizer"
    items = load_items(root / "data" / "eval_set.jsonl", ["arc_easy"], limit=2)
    assert len(items) == 2
    assert items[0].id.startswith("arc_easy")


def test_template_none_and_mismatch():
    raw = "Reply with B"
    assert render_prompt(None, raw, "none") == raw
    mismatched = render_prompt(None, raw, "mismatched")
    assert mismatched.startswith("<|begin_of_text|>")
    assert raw in mismatched
    assert MISMATCHED_LLAMA3.split("{user}")[0] in mismatched


def test_compare_markdown(tmp_path: Path):
    def blob(backend: str, template: str, acc: float) -> dict:
        return {
            "manifest": {
                "settings": {
                    "model_id": "Qwen/Qwen2.5-0.5B-Instruct",
                    "tokenizer_id": None,
                    "revision": None,
                    "backend": backend,
                    "chat_template": template,
                    "max_new_tokens": 96,
                    "seed": 0,
                    "dtype": "auto",
                },
                "hardware": {"gpu": "cpu"},
            },
            "tasks": {"overall": {"n": 10, "correct": int(acc * 10), "accuracy": acc}},
            "latency": {"ttft_ms_p95": 100.0, "tokens_per_sec_mean": 20.0},
        }

    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps(blob("hf", "tokenizer", 0.5)))
    b.write_text(json.dumps(blob("hf", "none", 0.2)))
    report = compare_runs(a, b)
    assert report["setting_diff"]["chat_template"]["a"] == "tokenizer"
    assert report["setting_diff"]["chat_template"]["b"] == "none"
    md = to_markdown(report)
    assert "chat_template" in md
    assert "0.2" in md
