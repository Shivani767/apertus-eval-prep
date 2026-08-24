import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "colab_install_vllm.py"


def _load():
    spec = importlib.util.spec_from_file_location("colab_install_vllm", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_wheel_pin_and_torch_skip():
    mod = _load()
    assert mod.VLLM_VER == "0.24.0"
    assert "cu129" in mod.VLLM_WHEEL
    assert "torch" in mod._SKIP_DIST
    assert "flashinfer-python" in mod._SKIP_DIST


def test_dist_name_strips_markers():
    mod = _load()
    assert mod._dist_name("cbor2") == "cbor2"
    assert mod._dist_name("transformers >= 5.5.3") == "transformers"
    assert mod._dist_name("fastapi[standard]>=0.133.0,<0.137.0") == "fastapi"
    assert mod._dist_name('llguidance>=1.7.0; platform_machine == "x86_64"') == "llguidance"
