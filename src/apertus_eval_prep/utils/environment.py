"""Environment and provenance probes that must never crash a run.

Every function degrades to ``None`` / ``"unknown"`` instead of raising: missing
git, a detached worktree, an absent GPU, or an uninstalled optional package must
not prevent an evaluation from producing an artifact.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

_GIT_TIMEOUT_S = 10


def _git(repo_root: Path, *args: str) -> str | None:
    """Run one git command; ``None`` when git is missing or the dir is not a repo."""
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def git_metadata(repo_root: str | Path | None = None) -> dict[str, Any]:
    """Commit/branch/dirty state of the checkout, gracefully absent when unavailable."""
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    commit = _git(root, "rev-parse", "HEAD")
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    porcelain = _git(root, "status", "--porcelain")
    available = commit is not None
    return {
        "available": available,
        "commit": commit,
        "branch": branch,
        "dirty": None if porcelain is None else bool(porcelain),
        "dirty_files": None if porcelain is None else len(porcelain.splitlines()),
    }


def python_metadata() -> dict[str, Any]:
    return {
        "version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "executable": sys.executable,
    }


def platform_metadata() -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
        "cpu_count": os.cpu_count(),
    }


def hardware_metadata(*, include_torch: bool = True) -> dict[str, Any]:
    """CPU/GPU facts. Torch is optional and imported only when requested."""
    info: dict[str, Any] = {"cpu_count": os.cpu_count(), "accelerator": "none"}
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        info["ram_gb"] = round(page_size * pages / (1024**3), 2)
    except (ValueError, OSError, AttributeError):
        info["ram_gb"] = None
    if not include_torch:
        return info
    try:
        import torch  # local import: torch is a heavy optional dependency

        info["torch"] = getattr(torch, "__version__", None)
        if torch.cuda.is_available():
            info["accelerator"] = "cuda"
            info["accelerator_name"] = torch.cuda.get_device_name(0)
            info["accelerator_count"] = torch.cuda.device_count()
        else:
            mps = getattr(torch.backends, "mps", None)
            if mps is not None and mps.is_available():
                info["accelerator"] = "mps"
                info["accelerator_name"] = "Apple MPS"
    except Exception:  # pragma: no cover - torch missing/broken is a normal offline case
        info.setdefault("torch", None)
    return info


def package_versions(names: list[str] | tuple[str, ...] | None = None) -> dict[str, str | None]:
    """Installed versions for the requested distributions (``None`` when absent)."""
    from importlib.metadata import PackageNotFoundError, version

    wanted = list(names) if names is not None else [
        "apertus-eval-prep",
        "torch",
        "transformers",
        "vllm",
        "pyyaml",
        "pytest",
    ]
    out: dict[str, str | None] = {}
    for name in wanted:
        try:
            out[name] = version(name)
        except Exception:
            out[name] = None
    return out


def environment_snapshot(repo_root: str | Path | None = None) -> dict[str, Any]:
    """One dict describing everything needed to interpret an artifact."""
    return {
        "git": git_metadata(repo_root),
        "python": python_metadata(),
        "platform": platform_metadata(),
        "hardware": hardware_metadata(),
        "packages": package_versions(),
    }
