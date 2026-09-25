"""Configuration loading, ``extends:`` resolution, and experiment-matrix expansion.

Two entry points matter:

``load_run_spec(path)``
    YAML → validated :class:`~apertus_eval_prep.core.schemas.RunSpec`, with
    optional ``extends:`` inheritance and dotted-path overrides from the CLI.

``load_experiment_spec(path)``
    YAML → :class:`~apertus_eval_prep.core.schemas.ExperimentSpec`, expanded
    deterministically into one baseline cell plus every factor combination.

Expansion is a pure function of the file: the same spec always yields the same
cells in the same order, which is what makes a matrix reproducible.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from apertus_eval_prep.core.errors import ConfigError, SchemaValidationError
from apertus_eval_prep.core.schemas import ExperimentSpec, RunSpec
from apertus_eval_prep.utils.serialization import read_yaml

#: Factor name -> dotted path inside the run spec. Dotted names in the YAML are
#: also accepted (``decoding.seed``) so new knobs need no code change here.
FACTOR_PATHS: dict[str, str] = {
    "seed": "decoding.seed",
    "temperature": "decoding.temperature",
    "top_p": "decoding.top_p",
    "max_new_tokens": "decoding.max_new_tokens",
    "prompt_id": "prompt.prompt_id",
    "prompt_template": "prompt.template",
    "prompt_version": "prompt.version",
    "system_prompt": "prompt.system_prompt",
    "quantization": "runtime.quantization",
    "precision": "runtime.precision",
    "device": "runtime.device",
    "backend": "adapter.kind",
    "adapter_kind": "adapter.kind",
    "model_id": "adapter.model_id",
    "model_revision": "adapter.revision",
    "revision": "adapter.revision",
    "limit": "task.limit",
    "split": "task.split",
    "task_kind": "task.kind",
    "task": "task.kind",
    "dataset": "task.path",
    "dataset_path": "task.path",
    "language": "dimensions.language",
    "locale": "dimensions.locale",
    "domain": "dimensions.domain",
    "deployment_environment": "dimensions.deployment_environment",
}

_MAX_EXTENDS_DEPTH = 10


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge mappings; override wins, scalars/lists replace."""
    out = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def set_path(data: dict[str, Any], dotted: str, value: Any) -> dict[str, Any]:
    """Return a deep copy of ``data`` with ``a.b.c`` set to ``value``."""
    if not dotted or any(not part for part in dotted.split(".")):
        raise ConfigError(f"invalid setting path {dotted!r}")
    out = deepcopy(data)
    cursor = out
    parts = dotted.split(".")
    for part in parts[:-1]:
        nxt = cursor.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cursor[part] = nxt
        cursor = nxt
    cursor[parts[-1]] = deepcopy(value)
    return out


def get_path(data: dict[str, Any], dotted: str, default: Any = None) -> Any:
    cursor: Any = data
    for part in dotted.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return default
        cursor = cursor[part]
    return cursor


def resolve_config_file(path: str | Path, _seen: tuple[Path, ...] = ()) -> dict[str, Any]:
    """Load a YAML config, resolving ``extends:`` chains with cycle detection."""
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"config not found: {config_path}")
    resolved_path = config_path.resolve()
    if resolved_path in _seen:
        chain = " -> ".join(str(p) for p in (*_seen, resolved_path))
        raise ConfigError(f"circular 'extends' chain: {chain}")
    if len(_seen) >= _MAX_EXTENDS_DEPTH:
        raise ConfigError(f"'extends' chain deeper than {_MAX_EXTENDS_DEPTH}: {config_path}")
    raw = read_yaml(config_path)
    parent = raw.pop("extends", None)
    if parent is None:
        return raw
    base = resolve_config_file(config_path.parent / str(parent), (*_seen, resolved_path))
    return deep_merge(base, raw)


def factor_path(factor: str) -> str:
    """Resolve a factor name (or explicit dotted path) to a spec path."""
    if factor in FACTOR_PATHS:
        return FACTOR_PATHS[factor]
    if "." in factor:
        return factor
    known = ", ".join(sorted(FACTOR_PATHS))
    raise ConfigError(f"unknown factor {factor!r}; use a dotted spec path or one of: {known}")


def load_run_spec(
    path: str | Path,
    overrides: dict[str, Any] | None = None,
    *,
    with_extends: bool = True,
) -> RunSpec:
    """Load and validate a run spec, applying dotted-path overrides last."""
    raw = resolve_config_file(path) if with_extends else read_yaml(path)
    if raw.get("factors") or raw.get("base"):
        raise ConfigError(f"{path} looks like an experiment spec; use load_experiment_spec() instead")
    spec_raw = raw
    for key, value in (overrides or {}).items():
        if value is None:
            continue
        spec_raw = set_path(spec_raw, factor_path(key) if "." not in key else key, value)
    return RunSpec.from_dict(spec_raw)


def load_experiment_spec(path: str | Path) -> ExperimentSpec:
    """Load and validate an experiment spec, including a Phase 8 study matrix."""
    raw = resolve_config_file(path)
    if "study" in raw and not isinstance(raw.get("experiment"), Mapping):
        from apertus_eval_prep.study.schema import StudySpec
        raw = StudySpec.from_dict(raw).to_experiment_dict()
    return ExperimentSpec.from_dict(raw)


def set_paths(data: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    """Apply a mapping of factor/level settings onto ``data`` (deep copy)."""
    out = deepcopy(data)
    for name, value in (settings or {}).items():
        out = set_path(out, factor_path(name) if "." not in name else name, value)
    return out


def _level_key(value: Any) -> str:
    return "null" if value is None else str(value).replace(" ", "_")


def cell_id_for(conditions: dict[str, Any]) -> str:
    """Deterministic, human-readable id for a factor combination."""
    if not conditions:
        return "baseline"
    return "_".join(f"{name}-{_level_key(conditions[name])}" for name in sorted(conditions))


@dataclass
class ExperimentCell:
    """One planned run inside an experiment matrix."""

    cell_id: str
    run_spec: RunSpec
    conditions: dict[str, Any] = field(default_factory=dict)
    is_baseline: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "is_baseline": self.is_baseline,
            "conditions": dict(self.conditions),
            "run_spec": self.run_spec.to_dict(),
        }


def _cell_run_spec(
    spec: ExperimentSpec, raw: dict[str, Any], conditions: dict[str, Any], *, is_baseline: bool
) -> RunSpec:
    payload = deepcopy(raw)
    run_block = payload.get("run") if isinstance(payload.get("run"), dict) else {}
    run_name = str(run_block.get("name") or payload.get("name") or spec.name)
    suffix = "baseline" if is_baseline else cell_id_for(conditions)
    payload = set_path(payload, "run.name", f"{run_name}-{suffix}")
    payload = set_path(payload, "run.experiment_id", spec.experiment_id)
    payload = set_path(payload, "run.parent_experiment_id", spec.experiment_id)
    try:
        run_spec = RunSpec.from_dict(payload)
    except SchemaValidationError as exc:
        raise ConfigError(f"experiment cell {suffix!r} is invalid: {exc}") from exc
    run_spec.conditions = dict(conditions)
    return run_spec


def expand_experiment(spec: ExperimentSpec) -> list[ExperimentCell]:
    """Expand an experiment into cells: baseline first, then every combination.

    The combination identical to the baseline levels is skipped (it *is* the
    baseline), and ``max_runs`` is enforced as a hard budget so a Cartesian
    explosion is always explicit rather than accidental.
    """
    base = spec.base
    baseline_raw = set_paths(base, spec.baseline)
    baseline_conditions = {
        name: spec.baseline.get(name, get_path(baseline_raw, factor_path(name)))
        for name in sorted(spec.factors)
    }

    cells: list[ExperimentCell] = [
        ExperimentCell(
            cell_id="baseline",
            run_spec=_cell_run_spec(spec, baseline_raw, baseline_conditions, is_baseline=True),
            conditions=baseline_conditions,
            is_baseline=True,
        )
    ]

    names = sorted(spec.factors)
    for combo in itertools.product(*(spec.factors[name] for name in names)):
        conditions = dict(zip(names, combo))
        if conditions == baseline_conditions:
            continue
        raw = set_paths(base, spec.baseline)
        for name in names:
            raw = set_path(raw, factor_path(name), conditions[name])
        cells.append(
            ExperimentCell(
                cell_id=cell_id_for(conditions),
                run_spec=_cell_run_spec(spec, raw, conditions, is_baseline=False),
                conditions=conditions,
            )
        )

    if len(cells) > spec.max_runs:
        raise ConfigError(
            f"experiment {spec.experiment_id!r} expands to {len(cells)} runs "
            f"> max_runs={spec.max_runs}; narrow the factors or raise max_runs explicitly"
        )
    return cells
