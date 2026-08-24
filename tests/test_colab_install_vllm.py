from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "scripts" / "colab_install_vllm.py").read_text(encoding="utf-8")


def test_required_covers_vllm_import_time_deps():
    # Wheel is --no-deps; hashing.py imports cbor2 on vLLM 0.24.
    assert '"cbor2"' in SCRIPT
    assert "VLLM_VER = \"0.24.0\"" in SCRIPT
