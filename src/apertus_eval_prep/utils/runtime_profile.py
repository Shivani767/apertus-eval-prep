"""Safe runtime/hardware profiling with no mandatory model dependencies."""
from __future__ import annotations

import importlib.util
import os
import platform
import sys
from typing import Any

from apertus_eval_prep.utils.environment import hardware_metadata, platform_metadata, python_metadata


def detect_runtime_environment() -> str:
    """Use explicit Colab markers only; do not infer Colab from a generic notebook."""
    if os.environ.get("COLAB_RELEASE_TAG") or os.environ.get("COLAB_GPU") or os.environ.get("COLAB_JUPYTER_IP"):
        return "google_colab"
    if "google.colab" in sys.modules:
        return "google_colab"
    return "local"


def profile_runtime(
    *, device: str | None = None, precision: str | None = None,
    quantization: str | None = None, include_torch: bool = True,
) -> dict[str, Any]:
    """Return partial runtime metadata; unavailable accelerator facts stay None."""
    runtime = detect_runtime_environment()
    hardware = hardware_metadata(include_torch=include_torch)
    torch_version = hardware.get("torch")
    cuda_version = None
    gpu_name = hardware.get("accelerator_name")
    gpu_count = hardware.get("accelerator_count")
    gpu_memory = None
    if include_torch and torch_version is not None:
        try:
            import torch  # optional, local to this profiling call
            cuda_version = getattr(getattr(torch, "version", None), "cuda", None)
            if getattr(torch, "cuda", None) and torch.cuda.is_available():
                gpu_count = torch.cuda.device_count()
                gpu_name = torch.cuda.get_device_name(0)
                properties = torch.cuda.get_device_properties(0)
                gpu_memory = round(properties.total_memory / (1024**3), 2)
        except Exception:
            pass
    return {
        "schema_version": "1.0",
        "runtime_environment": runtime,
        "os": platform_metadata(),
        "python": python_metadata(),
        "torch_version": torch_version,
        "cuda_version": cuda_version,
        "gpu_name": gpu_name,
        "gpu_count": gpu_count,
        "gpu_memory": gpu_memory,
        "gpu_memory_unit": "GiB" if gpu_memory is not None else None,
        "cpu_count": os.cpu_count(),
        "device_selection": device or "unavailable",
        "precision": precision or "unavailable",
        "quantization": quantization or "unavailable",
        "hardware_measured": bool(torch_version is not None),
        "hardware_measurement_status": "measured" if torch_version is not None else "unavailable",
        "latency_method": "client_side_wall_clock",
        "model_generation_latency": None,
        "end_to_end_workflow_latency": None,
    }


__all__ = ["detect_runtime_environment", "profile_runtime"]
