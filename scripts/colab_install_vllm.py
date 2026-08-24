#!/usr/bin/env python3
"""Install a Colab-safe vLLM wheel that matches torch 2.11 (T4 / cu128).

The GitHub wheel is installed with --no-deps so pip does not upgrade Colab torch.
Then every Requires-Dist from that wheel is installed, except CUDA/torch extras
that would replace 2.11. Pin lives here so `git pull` always wins over stale cells.
"""
from __future__ import annotations

import subprocess
import sys
import traceback
from importlib.metadata import requires


VLLM_VER = "0.24.0"
VLLM_WHEEL = (
    f"https://github.com/vllm-project/vllm/releases/download/v{VLLM_VER}/"
    f"vllm-{VLLM_VER}+cu129-cp38-abi3-manylinux_2_28_x86_64.whl"
)
TORCH_INDEX = "https://download.pytorch.org/whl/cu128"

# Do not let pip replace Colab's torch 2.11 / CUDA 12.8 stack.
_SKIP_DIST = {
    "torch",
    "torchvision",
    "torchaudio",
    "flashinfer-python",
    "flashinfer-cubin",
    "apache-tvm-ffi",
    "tilelang",
    "nvidia-cudnn-frontend",
    "nvidia-cutlass-dsl",
    "quack-kernels",
    "tokenspeed-mla",
    "humming-kernels",
    "numba",
}


def _run(cmd: list[str], check: bool = True) -> int:
    print("+", " ".join(cmd), flush=True)
    p = subprocess.run(cmd)
    if check and p.returncode != 0:
        raise SystemExit(f"command failed ({p.returncode}): {' '.join(cmd[:8])}")
    return p.returncode


def _dist_name(req: str) -> str:
    token = req.split(";", 1)[0].strip()
    for sep in ("[", " ", "<", ">", "=", "!"):
        if sep in token:
            token = token.split(sep, 1)[0]
    return token.strip().lower()


def _vllm_dep_specs() -> list[str]:
    specs: list[str] = []
    seen: set[str] = set()
    for raw in requires("vllm") or []:
        name = _dist_name(raw)
        if not name or name in _SKIP_DIST or name in seen:
            continue
        if "extra ==" in raw.replace(" ", "").lower():
            continue
        seen.add(name)
        specs.append(raw.split(";", 1)[0].strip())
    return specs


def _drop_vllm_modules() -> None:
    for name in list(sys.modules):
        if name == "vllm" or name.startswith("vllm."):
            del sys.modules[name]


def _import_vllm():
    from vllm import LLM, SamplingParams  # noqa: F401
    import torch as _t
    import vllm

    return vllm, _t


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
    _run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", VLLM_WHEEL])

    specs = _vllm_dep_specs()
    print(f"Installing {len(specs)} vLLM Requires-Dist (torch/CUDA extras skipped)", flush=True)
    if specs:
        _run([sys.executable, "-m", "pip", "install", "-q", *specs], check=False)

    _run(
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

    _drop_vllm_modules()
    last_missing = None
    vllm = _t = None
    for _ in range(12):
        try:
            vllm, _t = _import_vllm()
            break
        except ModuleNotFoundError as exc:
            missing = getattr(exc, "name", None)
            if not missing or missing == last_missing:
                traceback.print_exc()
                raise SystemExit(f"vLLM import still missing {missing!r}.") from exc
            last_missing = missing
            print(f"vLLM import needs {missing}; installing...", flush=True)
            _run([sys.executable, "-m", "pip", "install", "-q", missing], check=False)
            _drop_vllm_modules()
        except Exception:
            traceback.print_exc()
            raise SystemExit("vLLM import failed (full traceback above).")
    if vllm is None:
        raise SystemExit("vLLM import failed after installing missing deps.")

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
