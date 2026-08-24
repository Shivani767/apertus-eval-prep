import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_vllm_backend_module_parses():
    src = (ROOT / "src" / "apertus_eval_prep" / "backends" / "vllm_backend.py").read_text(
        encoding="utf-8"
    )
    ast.parse(src)
    assert 'startswith("no module named "vllm"")' not in src
