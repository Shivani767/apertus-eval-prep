"""Interaction-study subsystem (research Phase 2).

Builds crossed (factorial) experiment cells on top of the existing OFAT
architecture — ``sweep._base_cell`` / ``cell_to_run_config`` / ``run_id_for``
/ ``execute_cells`` — so interaction experiments share the registry, config
hashing, resume, and provenance machinery with OFAT. **OFAT is preserved
untouched**; this module only adds the multi-factor design layer.

Supported factor pairs (a minimally sufficient interaction screen):

  prompt x backend      (prompt_id x backend)
  prompt x quantization (prompt_id x quantization)
  backend x quantization
  prompt x decoding     (prompt_id x temperature/top_p)

Designs
-------
- ``full``: Cartesian product of the two axes (bounded by ``max_cells``).
- ``balanced``: deterministic marginal-balanced subset (fractional-factorial
  analogue) selected greedily under a seeded RNG; used when the full
  Cartesian product exceeds the budget. Marginal balance means every level of
  each axis appears approximately the same number of times — a defensible
  default for interaction detection when a full factorial is too expensive.

Every cell is a RunConfig-compatible dict plus provenance keys
``design`` / ``design_axes`` / ``interaction_id``, and the CLI stores the
same information in the registry row, so a factorial cell is never confused
with an OFAT cell.

Determinism: all selection uses ``random.Random(seed)``; identical inputs
produce identical cell lists (test-enforced).
"""

from __future__ import annotations

import itertools
import random
from typing import Any, Sequence

from apertus_eval_prep.sweep import _base_cell

#: canonical axis names -> RunConfig field names
FACTOR_FIELDS = {
    "prompt": "prompt_id",
    "backend": "backend",
    "quantization": "quantization",
    "decoding": "decoding",
}

#: factor pairs the interaction screen can measure (canonical order)
INTERACTION_PAIRS = (
    "prompt\u00d7backend",
    "prompt\u00d7quantization",
    "backend\u00d7quantization",
    "prompt\u00d7decoding",
)

DESIGNS = ("full", "balanced")


def _canonical_pair(pair: str) -> tuple[str, str]:
    """Normalize a pair string to two canonical axis names."""
    for name in INTERACTION_PAIRS:
        if pair == name:
            return name.split("\u00d7")
    raise ValueError(
        f"unknown interaction pair {pair!r}; use one of {INTERACTION_PAIRS}"
    )


def levels_for(study: dict[str, Any], factor: str) -> list[str]:
    """Resolve the level list of an axis from the study YAML.

    prompt -> study.factors.prompt_id
    backend -> study.factors.backend
    quantization -> study.factors.quantization
    decoding -> [greedy, sampled] derived from the control + sampled blocks.
    """
    if factor == "decoding":
        sampled = study.get("sampled") or {}
        if not sampled or not sampled.get("temperature"):
            raise ValueError("prompt\u00d7decoding needs a `sampled` block (temperature)")
        return ["greedy", "sampled"]
    factors = study.get("factors") or {}
    field = FACTOR_FIELDS[factor]
    levels = factors.get(field)
    if not levels:
        raise ValueError(f"study has no levels for factor {factor!r} (factors.{field})")
    return [str(l) for l in levels]


def _apply_level(cell: dict[str, Any], factor: str, level: str) -> None:
    """Mutate a base cell so the given axis takes `level`."""
    if factor == "prompt":
        cell["prompt_id"] = level
    elif factor == "backend":
        cell["backend"] = level
    elif factor == "quantization":
        cell["quantization"] = level
    elif factor == "decoding":
        if level == "greedy":
            cell["temperature"] = 0.0
            cell["top_p"] = 1.0
        else:
            sampled = cell.get("_sampled") or {}
            cell["temperature"] = float(sampled.get("temperature", 0.7))
            cell["top_p"] = float(sampled.get("top_p", 0.95))
    else:  # pragma: no cover (guarded by _canonical_pair)
        raise ValueError(factor)


def _base_cell_with_sampled(study: dict[str, Any], model_id: str) -> dict[str, Any]:
    """Base cell carrying the sampled-decoding levels it may need."""
    cell = _base_cell(study, model_id)
    cell["_sampled"] = study.get("sampled") or {}
    return cell


def all_level_combos(study: dict[str, Any], pair: str) -> list[dict[str, str]]:
    """Deterministic list of {axis: level} combos (full Cartesian)."""
    factor_a, factor_b = _canonical_pair(pair)
    names = (factor_a, factor_b)
    la, lb = levels_for(study, factor_a), levels_for(study, factor_b)
    return [dict(zip(names, vals)) for vals in itertools.product(la, lb)]


def balanced_select(
    combos: Sequence[dict[str, str]],
    k: int,
    *,
    seed: int = 0,
) -> list[dict[str, str]]:
    """Deterministic marginal-balanced subset of ``k`` combinations.

    Greedy rule: repeatedly add the combo whose next marginal load is
    smallest; ties are broken by a seeded RNG. Marginal load of a level is
    (current count + 1) / target_count, target_count = ceil(k / #levels) per
    axis. ``k`` >= len(combos) returns the full set; ``k`` = 0 raises.

    This is a heuristic (seeded, reproducible), not a statistically optimal
    fraction; the design is labelled ``balanced`` in provenance.
    """
    if k <= 0:
        raise ValueError(f"balanced selection needs k >= 1, got {k}")
    if k >= len(combos):
        return list(combos)
    rng = random.Random(seed)
    axes = sorted(combos[0].keys()) if combos else []
    levels = {a: sorted({c[a] for c in combos}) for a in axes}
    target = {a: (k + len(levels[a]) - 1) // len(levels[a]) for a in axes}
    counts = {a: {lv: 0 for lv in levels[a]} for a in axes}
    chosen: list[dict[str, str]] = []
    remaining = [c for c in combos]

    def _load(c: dict[str, str]) -> float:
        return sum((counts[a][c[a]] + 1.0) / target[a] for a in axes)

    while len(chosen) < k and remaining:
        min_load = min(_load(c) for c in remaining)
        candidates = [c for c in remaining if abs(_load(c) - min_load) < 1e-12]
        pick = candidates[0] if len(candidates) == 1 else rng.choice(candidates)
        remaining.remove(pick)
        chosen.append(pick)
        for a in axes:
            counts[a][pick[a]] += 1
    return chosen


def interaction_design(
    study: dict[str, Any],
    pair: str,
    *,
    design: str = "balanced",
    seed: int = 0,
    max_cells: int | None = None,
) -> dict[str, Any]:
    """One factor-pair design: which (a, b) combinations to run.

    Returns design metadata plus the combo list. ``max_cells`` is the hard
    per-model budget on crossed cells: the full Cartesian raises when it
    exceeds the budget, and ``balanced`` selects a subset instead.
    """
    if design not in DESIGNS:
        raise ValueError(f"design must be one of {DESIGNS}, got {design!r}")
    factor_a, factor_b = _canonical_pair(pair)
    full = all_level_combos(study, pair)
    total = len(full)
    if max_cells is not None and max_cells < 1:
        raise ValueError(f"max_cells must be >= 1, got {max_cells}")
    if design == "full" and max_cells is not None and total > max_cells:
        raise ValueError(
            f"interaction {pair} needs {total} cells > budget max_cells="
            f"{max_cells}; use design=balanced"
        )
    if design == "balanced" and max_cells is not None and total > max_cells:
        combos = balanced_select(full, max_cells, seed=seed)
    else:
        combos = full
    return {
        "pair": pair,
        "factor_a": factor_a,
        "factor_b": factor_b,
        "axis_levels": {
            factor_a: levels_for(study, factor_a),
            factor_b: levels_for(study, factor_b),
        },
        "design": design,
        "seed": seed,
        "max_cells": max_cells,
        "full_size": total,
        "selected_size": len(combos),
        "combos": combos,
        "provenance": "deterministic design; combos listed verbatim",
    }


def interaction_id(info: dict[str, Any]) -> str:
    """Stable short id for a design: pair|design|k-of-full|seed."""
    return (
        f"{info['pair']}|{info['design']}|"
        f"{info['selected_size']}-of-{info['full_size']}|seed{info['seed']}"
    )


def expand_interaction(
    study: dict[str, Any],
    pair: str,
    *,
    design: str = "balanced",
    seed: int = 0,
    max_cells: int | None = None,
    include_control: bool = True,
) -> list[dict[str, Any]]:
    """Cells for one interaction pair across every model in the study.

    Each cell carries ``design`` / ``design_axes`` / ``interaction_id`` so
    provenance shows the experiment type. Cells are deterministic given
    (study, pair, design, seed, max_cells) — test-enforced.
    """
    info = interaction_design(study, pair, design=design, seed=seed, max_cells=max_cells)
    factor_a, factor_b = info["factor_a"], info["factor_b"]
    cells: list[dict[str, Any]] = []
    for model in [str(m) for m in study["models"]]:
        if include_control:
            ctl = _base_cell_with_sampled(study, model)
            ctl["factor"] = "control"
            ctl["factor_level"] = "control"
            cells.append(ctl)
        for combo in info["combos"]:
            cell = _base_cell_with_sampled(study, model)
            for ax, lv in combo.items():
                _apply_level(cell, ax, lv)
                cell[ax] = lv  # provenance: explicit axis levels
            cell["factor"] = info["pair"]
            cell["factor_level"] = "+".join(f"{ax}={lv}" for ax, lv in combo.items())
            cell["design"] = info["design"]
            cell["design_axes"] = [factor_a, factor_b]
            cell["interaction_id"] = interaction_id(info)
            cells.append(cell)
    return cells


def interaction_study(
    study: dict[str, Any],
    *,
    pairs: Sequence[str] | None = None,
    design: str = "balanced",
    seed: int = 0,
    max_cells_per_pair: int | None = None,
    include_control: bool = True,
) -> dict[str, Any]:
    """Full interaction study: designs + all cells for the requested pairs.

    ``pairs`` defaults to the four supported pairs. Returns a dict with
    ``studies`` (per-pair design info) and ``cells`` (flat, runnable).
    """
    desired = [p for p in (pairs if pairs is not None else INTERACTION_PAIRS)]
    for p in desired:
        _canonical_pair(p)
    studies: dict[str, Any] = {}
    cells: list[dict[str, Any]] = []
    for pair in desired:
        info = interaction_design(
            study, pair, design=design, seed=seed, max_cells=max_cells_per_pair
        )
        info["interaction_id"] = interaction_id(info)
        studies[pair] = info
        cells.extend(
            expand_interaction(
                study, pair, design=design, seed=seed,
                max_cells=max_cells_per_pair, include_control=include_control,
            )
        )
    return {
        "experiment_type": "interaction_study",
        "design": design,
        "seed": seed,
        "max_cells_per_pair": max_cells_per_pair,
        "studies": studies,
        "cells": cells,
        "n_cells": len(cells),
        "n_models": len([str(m) for m in study["models"]]),
    }


def summarized_study(out: dict[str, Any]) -> dict[str, Any]:
    """Compact, JSON-serializable summary (designs only; cells listed as ids)."""
    return {
        "experiment_type": out["experiment_type"],
        "design": out["design"],
        "seed": out["seed"],
        "n_cells": out["n_cells"],
        "n_models": out["n_models"],
        "studies": {
            p: {
                "factor_a": s["factor_a"],
                "factor_b": s["factor_b"],
                "design": s["design"],
                "full_size": s["full_size"],
                "selected_size": s["selected_size"],
                "combos": s["combos"],
                "interaction_id": s.get("interaction_id"),
            }
            for p, s in out["studies"].items()
        },
    }