"""Validated declarative Phase 8 study configuration."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from apertus_eval_prep.core.config import resolve_config_file
from apertus_eval_prep.core.errors import ConfigError
from apertus_eval_prep.core.schemas import ComparisonSpec
from apertus_eval_prep.core.evidence import EVIDENCE_MODES, REAL_EVIDENCE_MODES, SYNTHETIC_EVIDENCE_MODES
from apertus_eval_prep.utils.hashing import hash_config
from apertus_eval_prep.utils.serialization import read_yaml


def _map(value: Any, name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ConfigError(f"{name} must be a mapping")
    return dict(value)


def _levels(value: Any, name: str) -> None:
    if value is not None and (not isinstance(value, (list, tuple)) or not value):
        raise ConfigError(f"{name} must be a non-empty list")


@dataclass
class StudySpec:
    study_id: str
    study_title: str
    research_question: str
    evidence_mode: str
    hypothesis_ids: list[str] = field(default_factory=list)
    planned_sample_counts: dict[str, int] = field(default_factory=dict)
    protocol_path: str | None = None
    preregistration_path: str | None = None
    investigator: str | None = None
    deviation_log_path: str | None = None
    matrix: dict[str, Any] = field(default_factory=dict)
    base: dict[str, Any] = field(default_factory=dict)
    experiment: dict[str, Any] = field(default_factory=dict)
    suites: dict[str, Any] = field(default_factory=dict)
    human_review: dict[str, Any] = field(default_factory=dict)
    release_gates: dict[str, Any] = field(default_factory=dict)
    comparison: dict[str, Any] = field(default_factory=dict)
    allow_mock: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_real_study(self) -> bool:
        return self.evidence_mode in REAL_EVIDENCE_MODES

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> "StudySpec":
        if not isinstance(raw, Mapping):
            raise ConfigError("study config must be a mapping")
        data = dict(raw)
        study = _map(data.get("study"), "study")
        matrix = _map(data.get("matrix") or data.get("factors") or study.get("matrix"), "study.matrix")
        base = _map(data.get("base"), "study.base")
        experiment = _map(data.get("experiment"), "study.experiment")
        mode = str(study.get("evidence_mode") or data.get("evidence_mode") or "UNKNOWN").upper()
        if mode not in EVIDENCE_MODES:
            raise ConfigError(f"unsupported study evidence mode: {mode}")
        allow_mock = bool(data.get("allow_mock", study.get("allow_mock", False)))
        comparison = ComparisonSpec.from_dict(
            data.get("comparison") or study.get("comparison")
        ).to_dict()
        adapter = _map(base.get("adapter"), "study.base.adapter")
        adapter_kind = str(adapter.get("kind", "")).lower()
        if mode in SYNTHETIC_EVIDENCE_MODES and not allow_mock:
            raise ConfigError("MOCK/SYNTHETIC study evidence requires explicit allow_mock=true")
        if mode not in SYNTHETIC_EVIDENCE_MODES and adapter_kind == "mock":
            raise ConfigError("real-study config cannot use a mock adapter; set allow_mock only for demos")
        if mode == "MOCK" and adapter_kind != "mock":
            raise ConfigError("MOCK study evidence requires a mock adapter")
        base_evidence = _map(base.get("evidence"), "study.base.evidence")
        base_mode = str(base_evidence.get("mode") or mode).upper()
        if base_mode != mode:
            raise ConfigError("study and base evidence modes must match")
        counts = _map(study.get("planned_sample_counts") or data.get("planned_sample_counts"), "study.planned_sample_counts")
        for key, value in counts.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) < 1 or float(value) != int(value):
                raise ConfigError(f"study.planned_sample_counts.{key} must be a positive whole number")
        for key in ("models", "prompt_templates", "seeds", "dtype", "quantization"):
            _levels(matrix.get(key), f"study.matrix.{key}")

        return cls(
            study_id=str(study.get("study_id") or data.get("study_id") or "phase8-study"),
            study_title=str(study.get("study_title") or data.get("study_title") or "Phase 8 study"),
            research_question=str(study.get("research_question") or data.get("research_question") or ""),
            evidence_mode=mode,
            hypothesis_ids=[str(x) for x in study.get("hypothesis_ids", data.get("hypothesis_ids", []))],
            planned_sample_counts={str(k): int(v) for k, v in counts.items()},
            protocol_path=study.get("protocol_path") or data.get("protocol_path"),
            preregistration_path=study.get("preregistration_path") or data.get("preregistration_path"),
            investigator=study.get("investigator") or data.get("investigator"),
            deviation_log_path=study.get("deviation_log_path") or data.get("deviation_log_path"),
            matrix=matrix, base=base, experiment=experiment,
            suites=_map(data.get("suites") or study.get("suites"), "study.suites"),
            human_review=_map(data.get("human_review") or study.get("human_review"), "study.human_review"),
            release_gates=_map(data.get("release_gates") or study.get("release_gates"), "study.release_gates"),
            comparison=comparison, allow_mock=allow_mock, raw=data,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0", "study_id": self.study_id, "study_title": self.study_title,
            "research_question": self.research_question, "hypothesis_ids": list(self.hypothesis_ids),
            "planned_sample_counts": dict(self.planned_sample_counts), "protocol_path": self.protocol_path,
            "preregistration_path": self.preregistration_path, "investigator": self.investigator,
            "deviation_log_path": self.deviation_log_path, "evidence_mode": self.evidence_mode,
            "allow_mock": self.allow_mock, "matrix": dict(self.matrix), "base": dict(self.base),
            "experiment": dict(self.experiment), "suites": dict(self.suites),
            "human_review": dict(self.human_review), "release_gates": dict(self.release_gates),
            "comparison": dict(self.comparison),
        }

    def config_hash(self) -> str:
        return hash_config(self.to_dict())

    def to_experiment_dict(self) -> dict[str, Any]:
        """Convert the declarative study matrix to the existing experiment schema."""
        aliases = {
            "models": "model_id", "prompt_templates": "prompt_template", "seeds": "seed",
            "dtype": "precision", "quantization": "quantization",
        }
        factors: dict[str, list[Any]] = {}
        baseline: dict[str, Any] = {}
        for name, levels in self.matrix.items():
            if name == "decoding":
                decoding = _map(levels, "study.matrix.decoding")
                for key, values in decoding.items():
                    if not isinstance(values, list) or not values:
                        raise ConfigError(f"study.matrix.decoding.{key} must be a non-empty list")
                    factors[key] = list(values)
                    baseline[key] = values[0]
                continue
            factor = aliases.get(str(name), str(name))
            values = list(levels) if isinstance(levels, (list, tuple)) else [levels]
            factors[factor] = values
            baseline[factor] = values[0]
        return {"experiment": {
            "name": self.study_id, "id": self.study_id, "base": self.base,
            "baseline": baseline, "factors": factors,
            "max_runs": int(self.raw.get("max_runs", 64)), "comparison": self.comparison,
        }}


def load_study_config(path: str | Path) -> StudySpec:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"study config not found: {path}")
    raw = resolve_config_file(path) if path.suffix in {".yaml", ".yml"} else read_yaml(path)
    return StudySpec.from_dict(raw)


__all__ = ["StudySpec", "load_study_config"]
