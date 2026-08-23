#!/usr/bin/env python3
"""Install a Colab-safe vLLM wheel that matches torch 2.11 (T4 / cu128).

Pin lives here so `git pull` + this script always wins over stale Colab UI cells.
"""
from __future__ import annotations

import subprocess
import sys
import traceback


VLLM_VER = "0.24.0"
VLLM_WHEEL = (
    f"https://github.com/vllm-project/vllm/releases/download/v{VLLM_VER}/"
    f"vllm-{VLLM_VER}+cu129-cp38-abi3-manylinux_2_28_x86_64.whl"
)
TORCH_INDEX = "https://download.pytorch.org/whl/cu128"

# Minimal deps to import LLM / SamplingParams for text generate.
_REQUIRED = [
    "transformers>=4.56.0",
    "tokenizers>=0.21.1",
    "sentencepiece",
    "protobuf",
    "fastapi",
    "uvicorn[standard]",
    "openai",
    "prometheus_client",
    "einops",
    "cloudpickle",
    "pyzmq",
    "msgspec",
    "blake3",
    "pillow",
    "tiktoken",
    "huggingface_hub",
    "aiohttp",
    "filelock",
    "psutil",
    "ninja",
    "gguf",
    "importlib_metadata",
    "partial_json_parser",
    "python-json-logger",
    "watchfiles",
]

# Nice-to-have; skip individually if a pin fails on Colab.
_OPTIONAL = [
    "prometheus-fastapi-instrumentator",
    "lm-format-enforcer>=0.10.11",
    "outlines_core==0.2.11",
    "xgrammar",
    "llguidance",
    "mistral_common>=1.8.8",
    "compressed-tensors",
    "depyf",
    "pybase64",
    "ray>=2.48.0",
]


def _pip(args: list[str], check: bool = True) -> bool:
    cmd = [sys.executable, "-m", "pip", *args]
    print("+", " ".join(cmd), flush=True)
    p = subprocess.run(cmd, text=True, capture_output=True)
    if p.stdout.strip():
        print(p.stdout[-2000:], flush=True)
    if p.returncode != 0:
        print(p.stderr[-3000:], flush=True)
        if check:
            raise RuntimeError(f"pip failed ({p.returncode}): {' '.join(args[:6])}...")
        return False
    return True


def main() -> None:
    import torch

    if not torch.cuda.is_available():
        raise SystemExit("No GPU. Runtime → Change runtime type → T4 GPU, then rerun.")
    print(torch.cuda.get_device_name(0), "torch", torch.__version__, "cuda", torch.version.cuda, flush=True)
    if not str(torch.__version__).startswith("2.11"):
        raise SystemExit(
            f"Expected Colab torch 2.11.x, got {torch.__version__}. "
            "Runtime → Disconnect and delete runtime, reconnect with T4."
        )

    print(f"Installing pinned wheel: {VLLM_WHEEL}", flush=True)
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "vllm"], check=False)
    _pip(["install", "-q", "--no-deps", VLLM_WHEEL], check=True)

    _pip(["install", "-q", *_REQUIRED], check=True)
    for pkg in _OPTIONAL:
        _pip(["install", "-q", pkg], check=False)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-q",
            "torchvision==0.26.0+cu128",
            "torchaudio==2.11.0+cu128",
            "--index-url",
            TORCH_INDEX,
        ],
        check=False,
    )

    for name in list(sys.modules):
        if name == "vllm" or name.startswith("vllm."):
            del sys.modules[name]

    try:
        from vllm import LLM, SamplingParams  # noqa: F401
        import vllm
        import torch as _t
    except Exception:
        traceback.print_exc()
        raise SystemExit("vLLM import failed after install (see traceback above).")

    print("OK vllm", getattr(vllm, "__version__", "?"), "torch", _t.__version__, flush=True)
    if not str(_t.__version__).startswith("2.11"):
        raise SystemExit(f"torch was upgraded away from 2.11: {_t.__version__}")
    if not str(getattr(vllm, "__version__", "")).startswith("0.24"):
        raise SystemExit(
            f"Wrong vLLM version {getattr(vllm, '__version__', '?')}; expected 0.24.x"
        )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
