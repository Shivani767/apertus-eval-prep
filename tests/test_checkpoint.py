from pathlib import Path

from apertus_eval_prep.backends import Generation
from apertus_eval_prep.checkpoint import append_partial, load_partial, start_partial
from apertus_eval_prep.config import RunConfig
from apertus_eval_prep import run_eval as run_eval_mod
from apertus_eval_prep.registry import config_hash
from apertus_eval_prep.run_eval import run_eval


ROOT = Path(__file__).resolve().parents[1]


def _cfg() -> RunConfig:
    return RunConfig(
        model_id="dummy",
        tokenizer_id=None,
        revision=None,
        backend="hf",
        chat_template="none",
        system_prompt=None,
        max_new_tokens=8,
        seed=0,
        dtype="auto",
        data_path="tests/fixtures/official_tiny.jsonl",
        tasks=["arc_easy", "gsm8k"],
        limit=None,
        batch_size=1,
        quantization="none",
        temperature=0.0,
        top_p=1.0,
        prompt_id=None,
        fewshot_path=None,
        experiment_id="test",
        run_id="ckpt-test",
    )


class _Tok:
    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
        return messages[-1]["content"]


class _Backend:
    tokenizer = _Tok()
    device = "cpu"
    queue: list[str] = []

    def generate_one(self, prompt: str, max_new_tokens: int) -> Generation:
        text = type(self).queue.pop(0)
        return Generation(text=text, ttft_ms=1.0, e2e_ms=2.0, num_new_tokens=1)


def _row(item_id: str, task: str, gold: str, pred: str) -> dict:
    return {
        "id": item_id,
        "task": task,
        "language": "en",
        "gold": gold,
        "predicted": pred,
        "correct": True,
        "generation": pred,
        "ttft_ms": 1.0,
        "e2e_ms": 2.0,
        "num_new_tokens": 1,
        "tokens_per_sec": 500.0,
        "prompt_chars": 8,
    }


def test_fingerprint_mismatch_drops_file(tmp_path: Path):
    path = tmp_path / "x.partial.jsonl"
    start_partial(path, "aaa", 2)
    append_partial(path, {"id": "a", "correct": True})
    assert load_partial(path, "bbb") == []
    assert not path.exists()


def test_resume_skips_scored_items(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(run_eval_mod, "_backend", lambda cfg: _Backend())
    ckpt = tmp_path / "run.partial.jsonl"
    fp = config_hash(_cfg().comparable_settings())
    start_partial(ckpt, fp, 4)
    append_partial(ckpt, _row("arc_easy/t1", "arc_easy", "B", "B"))
    append_partial(ckpt, _row("arc_easy/t2", "arc_easy", "A", "A"))

    _Backend.queue = ["12", "9"]
    payload = run_eval(_cfg(), ROOT, checkpoint_path=ckpt)
    assert _Backend.queue == []
    assert payload["tasks"]["overall"]["n"] == 4
    assert payload["tasks"]["overall"]["correct"] == 4
    assert [r["id"] for r in payload["items"]] == [
        "arc_easy/t1",
        "arc_easy/t2",
        "gsm8k/t1",
        "gsm8k/t2",
    ]
    assert not ckpt.exists()
