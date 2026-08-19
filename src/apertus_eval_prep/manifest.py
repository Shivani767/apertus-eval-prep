from __future__ import annotations

import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _git(repo_root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _pkg_version(name: str) -> str | None:
    try:
        from importlib.metadata import version

        return version(name)
    except Exception:
        return None


def hardware_block() -> dict[str, Any]:
    gpu = "none"
    cuda = False
    try:
        import torch

        cuda = bool(torch.cuda.is_available())
        if cuda:
            gpu = torch.cuda.get_device_name(0)
        elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            gpu = "Apple MPS"
    except Exception:
        pass
    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": sys.version.split()[0],
        "gpu": gpu,
        "cuda": cuda,
    }


def build_manifest(repo_root: Path, settings: dict[str, Any]) -> dict[str, Any]:
    commit = _git(repo_root, "rev-parse", "HEAD")
    dirty = _git(repo_root, "status", "--porcelain")
    return {
        "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": commit,
        "git_dirty": bool(dirty),
        "packages": {
            "torch": _pkg_version("torch"),
            "transformers": _pkg_version("transformers"),
            "vllm": _pkg_version("vllm"),
            "apertus_eval_prep": _pkg_version("apertus-eval-prep"),
        },
        "hardware": hardware_block(),
        "settings": settings,
    }
