from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from apertus_eval_prep.config import RunConfig


def load_study(path: str | Path) -> dict[str, Any]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not raw.get("models"):
        raise ValueError("study yaml needs a models list")
    if not raw.get("control"):
        raise ValueError("study yaml needs a control block")
    return raw


def _matches_skip(cell: dict[str, Any], skip: dict[str, Any]) -> bool:
    return all(cell.get(k) == v for k, v in skip.items())


def _base_cell(study: dict[str, Any], model_id: str) -> dict[str, Any]:
    control = study["control"]
    cell = {
        "model_id": model_id,
        "tokenizer_id": study.get("tokenizer_id"),
        "revision": study.get("revision"),
        "backend": control.get("backend", "hf"),
        "chat_template": control.get("chat_template", study.get("chat_template", "tokenizer")),
        "system_prompt": study.get("system_prompt"),
        "max_new_tokens": int(study.get("max_new_tokens", 256)),
        "seed": int(control.get("seed", 0)),
        "dtype": str(study.get("dtype", "auto")),
        "data_path": str(study.get("data_path", "data/official/eval_set.jsonl")),
        "tasks": list(study.get("tasks") or []),
        "limit": study.get("limit"),
        "batch_size": int(study.get("batch_size", 1)),
        "quantization": str(control.get("quantization", "none")),
        "temperature": float(control.get("temperature", 0.0)),
        "top_p": float(control.get("top_p", 1.0)),
        "prompt_id": control.get("prompt_id", "default"),
        "fewshot_path": study.get("fewshot_path"),
        "experiment_id": study.get("experiment_id"),
        "run_id": None,
        "paraphrase_id": control.get("paraphrase_id", "orig"),
        "factor": "control",
        "factor_level": "control",
    }
    return cell


def expand_ofat(study: dict[str, Any], profile: str | None = None) -> list[dict[str, Any]]:
    """One-factor-at-a-time cells around control, plus optional sampled seed arm."""
    models = [str(m) for m in study["models"]]
    control = study["control"]
    cells: list[dict[str, Any]] = []

    for model in models:
        cells.append(_base_cell(study, model))

    factors: dict[str, list] = dict(study.get("factors") or {})
    for factor, levels in factors.items():
        control_val = control.get(factor)
        for level in levels:
            if level == control_val:
                continue
            for model in models:
                cell = _base_cell(study, model)
                cell[factor] = level
                cell["factor"] = factor
                cell["factor_level"] = str(level)
                if factor == "paraphrase_id":
                    cell["data_path"] = str(
                        study.get("paraphrase_data_path", "data/paraphrase_set.jsonl")
                    )
                    if study.get("paraphrase_tasks"):
                        cell["tasks"] = list(study["paraphrase_tasks"])
                cells.append(cell)

    sampled = study.get("sampled") or {}
    if sampled:
        temp = float(sampled.get("temperature", 0.7))
        top_p = float(sampled.get("top_p", control.get("top_p", 1.0)))
        for seed in sampled.get("seeds") or []:
            for model in models:
                cell = _base_cell(study, model)
                cell["temperature"] = temp
                cell["top_p"] = top_p
                cell["seed"] = int(seed)
                cell["factor"] = "sampled"
                cell["factor_level"] = f"t{temp}_seed{seed}"
                cells.append(cell)

    if profile:
        profiles = study.get("profiles") or {}
        spec = profiles.get(profile)
        if spec is None:
            raise ValueError(f"unknown profile {profile!r}; have {sorted(profiles)}")
        skip_list = spec.get("skip") or []
        cells = [c for c in cells if not any(_matches_skip(c, s) for s in skip_list)]

    return cells


def cell_to_run_config(cell: dict[str, Any], overrides: dict[str, Any] | None = None) -> RunConfig:
    raw = deepcopy(cell)
    raw.pop("factor", None)
    raw.pop("factor_level", None)
    if overrides:
        for key, value in overrides.items():
            if value is not None:
                raw[key] = value
    tmp = {
        "model_id": raw["model_id"],
        "tokenizer_id": raw.get("tokenizer_id"),
        "revision": raw.get("revision"),
        "backend": raw.get("backend", "hf"),
        "chat_template": raw.get("chat_template", "tokenizer"),
        "system_prompt": raw.get("system_prompt"),
        "max_new_tokens": raw.get("max_new_tokens", 256),
        "seed": raw.get("seed", 0),
        "dtype": raw.get("dtype", "auto"),
        "data_path": raw.get("data_path"),
        "tasks": raw.get("tasks") or [],
        "limit": raw.get("limit"),
        "batch_size": raw.get("batch_size", 1),
        "quantization": raw.get("quantization", "none"),
        "temperature": raw.get("temperature", 0.0),
        "top_p": raw.get("top_p", 1.0),
        "prompt_id": raw.get("prompt_id"),
        "fewshot_path": raw.get("fewshot_path"),
        "experiment_id": raw.get("experiment_id"),
        "run_id": raw.get("run_id"),
        "paraphrase_id": raw.get("paraphrase_id"),
    }
    from apertus_eval_prep.config import VALID_BACKENDS, VALID_QUANTIZATION, VALID_TEMPLATES

    cfg = RunConfig(
        model_id=tmp["model_id"],
        tokenizer_id=tmp.get("tokenizer_id"),
        revision=tmp.get("revision"),
        backend=str(tmp.get("backend", "hf")),
        chat_template=str(tmp.get("chat_template", "tokenizer")),
        system_prompt=tmp.get("system_prompt"),
        max_new_tokens=int(tmp.get("max_new_tokens", 256)),
        seed=int(tmp.get("seed", 0)),
        dtype=str(tmp.get("dtype", "auto")),
        data_path=str(tmp.get("data_path")),
        tasks=list(tmp.get("tasks") or []),
        limit=tmp.get("limit"),
        batch_size=int(tmp.get("batch_size", 1)),
        quantization=str(tmp.get("quantization", "none")),
        temperature=float(tmp.get("temperature", 0.0)),
        top_p=float(tmp.get("top_p", 1.0)),
        prompt_id=tmp.get("prompt_id"),
        fewshot_path=tmp.get("fewshot_path"),
        experiment_id=tmp.get("experiment_id"),
        run_id=tmp.get("run_id"),
        paraphrase_id=tmp.get("paraphrase_id"),
    )
    if cfg.backend not in VALID_BACKENDS:
        raise ValueError(cfg.backend)
    if cfg.chat_template not in VALID_TEMPLATES:
        raise ValueError(cfg.chat_template)
    if cfg.quantization not in VALID_QUANTIZATION:
        raise ValueError(cfg.quantization)
    if cfg.limit is not None:
        cfg.limit = int(cfg.limit)
    return cfg


def run_id_for(cell: dict[str, Any], digest: str) -> str:
    model = str(cell["model_id"]).split("/")[-1]
    factor = cell.get("factor", "control")
    level = str(cell.get("factor_level", "control")).replace("/", "-")
    return f"{model}_{factor}_{level}_{digest}"


def execute_sweep(
    study_path: Path,
    repo_root: Path,
    out_dir: Path,
    registry_path: Path,
    profile: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    force: bool = False,
    only_model: str | None = None,
    only_factor: str | None = None,
) -> list[dict[str, Any]]:
    from apertus_eval_prep.registry import append_registry, completed_hashes, config_hash, load_registry
    from apertus_eval_prep.run_eval import run_eval

    out_dir = Path(out_dir)
    if not out_dir.is_absolute():
        out_dir = repo_root / out_dir
    registry_path = Path(registry_path)
    if not registry_path.is_absolute():
        registry_path = repo_root / registry_path

    study = load_study(study_path)
    cells = expand_ofat(study, profile=profile)
    if only_model:
        cells = [c for c in cells if c["model_id"] == only_model]
        if not cells:
            raise SystemExit(f"no cells for model {only_model!r} under this profile")
    if only_factor:
        cells = [c for c in cells if c.get("factor") == only_factor]
        if not cells:
            raise SystemExit(f"no cells for factor {only_factor!r} under this profile")
    done = completed_hashes(load_registry(registry_path))
    planned: list[dict[str, Any]] = []
    for cell in cells:
        if limit is not None:
            cell = dict(cell)
            cell["limit"] = limit
        cfg = cell_to_run_config(cell)
        digest = config_hash(cfg.comparable_settings())
        rid = run_id_for(cell, digest)
        cfg.run_id = rid
        entry = {
            "run_id": rid,
            "config_hash": digest,
            "model_id": cfg.model_id,
            "factor": cell.get("factor"),
            "factor_level": cell.get("factor_level"),
            "path": str((out_dir / f"{rid}.json").relative_to(repo_root)),
            "skipped": digest in done and not force,
        }
        planned.append(entry)
        print(
            f"{'skip' if entry['skipped'] else 'run '} {rid} factor={cell.get('factor')}={cell.get('factor_level')}",
            flush=True,
        )
        if dry_run or entry["skipped"]:
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        ckpt = out_dir / f"{rid}.partial.jsonl"
        payload = run_eval(cfg, repo_root, checkpoint_path=ckpt)
        payload["factor"] = cell.get("factor")
        payload["factor_level"] = cell.get("factor_level")
        payload["config_hash"] = digest
        out_path = out_dir / f"{rid}.json"
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        try:
            rel = str(out_path.relative_to(repo_root))
        except ValueError:
            rel = str(out_path)
        append_registry(
            registry_path,
            {
                "run_id": rid,
                "config_hash": digest,
                "experiment_id": cfg.experiment_id,
                "model_id": cfg.model_id,
                "factor": cell.get("factor"),
                "factor_level": cell.get("factor_level"),
                "path": rel,
                "status": "ok",
                "git_commit": payload["manifest"].get("git_commit"),
                "hardware": payload["manifest"].get("hardware"),
                "overall": payload.get("tasks", {}).get("overall"),
            },
        )
        done.add(digest)
    return planned
