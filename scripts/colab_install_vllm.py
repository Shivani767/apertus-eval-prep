#!/usr/bin/env python3
"""Install a Colab-safe vLLM wheel that matches torch 2.11 (T4 / cu128).

Colab notebook cells go stale after git pull — keep the pin HERE so
`python scripts/colab_install_vllm.py` always uses the committed version.
"""
from __future__ import annotations

import os
import subprocess
import sys


VLLM_VER = "0.24.0"
VLLM_WHEEL = (
    f"https://github.com/vllm-project/vllm/releases/download/v{VLLM_VER}/"
    f"vllm-{VLLM_VER}+cu129-cp38-abi3-manylinux_2_28_x86_64.whl"
)
TORCH_INDEX = "https://download.pytorch.org/whl/cu128"

# Non-torch deps for vllm 0.24 (torch stays Colab's 2.11.0+cu128).
_EXTRA_DEPS = [
    "transformers>=4.56.0",
    "tokenizers>=0.21.1",
    "sentencepiece",
    "protobuf",
    "fastapi",
    "uvicorn[standard]",
    "openai",
    "prometheus_client",
    "prometheus-fastapi-instrumentator",
    "lm-format-enforcer>=0.10.11",
    "outlines_core==0.2.11",
    "xgrammar",
    "llguidance",
    "gguf",
    "mistral_common>=1.8.8",
    "compressed-tensors",
    "depyf",
    "cloudpickle",
    "watchfiles",
    "python-json-logger",
    "einops",
    "importlib_metadata",
    "partial_json_parser",
    "pyzmq",
    "msgspec",
    "blake3",
    "pybase64",
    "pillow",
    "tiktoken",
    "huggingface_hub",
    "aiohttp",
    "filelock",
    "psutil",
    "ray>=2.48.0",
    "ninja",
]


def _pip(*args: str) -> None:
    cmd = [sys.executable, "-m", "pip", *args]
    print("+", " ".join(cmd), flush=True)
    p = subprocess.run(cmd, text=True, capture_output=True)
    if p.stdout.strip():
        print(p.stdout[-1200:], flush=True)
    if p.returncode != 0:
        print(p.stderr[-2000:], flush=True)
        raise SystemExit(f"pip failed ({p.returncode})")


def main() -> None:
    import torch

    if not torch.cuda.is_available():
        raise SystemExit("No GPU. Runtime → Change runtime type → T4 GPU, then rerun.")
    print(torch.cuda.get_device_name(0), "torch", torch.__version__, "cuda", torch.version.cuda)
    if not str(torch.__version__).startswith("2.11"):
        raise SystemExit(
            f"Expected Colab torch 2.11.x, got {torch.__version__}. "
            "Runtime → Disconnect and delete runtime, reconnect with T4."
        )

    print(f"Installing pinned wheel: {VLLM_WHEEL}", flush=True)
    if "0.27" in VLLM_WHEEL:
        raise SystemExit("Refusing to install vLLM 0.27 on Colab torch 2.11.")

    subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "vllm"], check=False)
    # --no-deps: do not let pip replace Colab torch.
    _pip("install", "-q", "--no-deps", VLLM_WHEEL)
    _pip("install", "-q", *_EXTRA_DEPS)
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

    from vllm import LLM, SamplingParams  # noqa: F401
    import vllm
    import torch as _t

    print("OK vllm", getattr(vllm, "__version__", "?"), "torch", _t.__version__, flush=True)
    if not str(_t.__version__).startswith("2.11"):
        raise SystemExit(f"torch was upgraded away from 2.11: {_t.__version__}")
    if not str(getattr(vllm, "__version__", "")).startswith("0.24"):
        raise SystemExit(
            f"Wrong vLLM version {getattr(vllm, '__version__', '?')}; expected 0.24.x"
        )


if __name__ == "__main__":
    main()
