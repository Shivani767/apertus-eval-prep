"""Reproducible LLM evaluation and release-readiness platform.

The legacy flat-module harness remains available; these exports describe the
typed, offline-first platform layer.
"""
from .core.config import load_experiment_spec, load_run_spec
from .core.runner import RunResult, run_config, run_evaluation
from .core.schemas import ExperimentSpec, RunSpec

__version__ = "0.5.0"

__all__ = [
    "RunResult", "RunSpec", "ExperimentSpec", "load_run_spec", "load_experiment_spec",
    "run_evaluation", "run_config",
]
