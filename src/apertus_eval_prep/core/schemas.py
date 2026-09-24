"""Typed, validated schemas for platform runs and experiments.

Validation is explicit (no hidden coercion beyond documented casts) and every
failure names the offending field path via :class:`SchemaValidationError`.

Optional future dimensions (``language``, ``locale``, ``domain``,
``risk_category``, ``deployment_environment``) exist on every task/run so the
platform can grow beyond general-English evaluation without a schema break.
The core evaluation target remains general English; these dimensions default to
``None`` and never gate execution.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from apertus_eval_prep.core.errors import SchemaValidationError
from apertus_eval_prep.utils.hashing import hash_config

ADAPTER_KINDS: tuple[str, ...] = ("mock", "local", "openai_compatible")
TASK_KINDS: tuple[str, ...] = ("static_qa", "rag_episode", "agent_episode")
JUDGE_MODES: tuple[str, ...] = ("rules", "adapter")
QUANTIZATIONS: tuple[str, ...] = ("none", "int8", "int4")
DIMENSION_KEYS: tuple[str, ...] = (
    "language",
    "locale",
    "domain",
    "risk_category",
    "deployment_environment",
)
SYNTHETIC_EVIDENCE_CLASSES: frozenset[str] = frozenset({"MOCK", "DEMONSTRATION"})

#: Keys that never contribute to the semantic config hash (they describe the
#: invocation, not the evaluation).
VOLATILE_CONFIG_KEYS: tuple[str, ...] = ("run_name", "parent_experiment_id")


def _require_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SchemaValidationError(field_name, f"expected a mapping, got {type(value).__name__}")
    return dict(value)


def _first(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _default(value: Any, fallback: Any) -> Any:
    """Return ``value`` when supplied, including valid false-y values."""
    return fallback if value is None else value


def as_str(
    value: Any,
    field_name: str,
    *,
    default: str | None = None,
    required: bool = False,
    allow_empty: bool = False,
) -> str | None:
    if value is None:
        if required and default is None:
            raise SchemaValidationError(field_name, "is required")
        return default
    text = str(value).strip()
    if not text:
        if required and default is None:
            raise SchemaValidationError(field_name, "must not be empty")
        if not allow_empty:
            return default
    return text or default


def as_int(
    value: Any, field_name: str, *, default: int | None = None, minimum: int | None = None
) -> int | None:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise SchemaValidationError(field_name, f"expected an integer, got {type(value).__name__}")
    try:
        out = int(value)
    except (TypeError, ValueError) as exc:
        raise SchemaValidationError(field_name, f"expected an integer, got {value!r}") from exc
    if isinstance(value, float) and not float(value).is_integer():
        raise SchemaValidationError(field_name, f"expected a whole number, got {value!r}")
    if minimum is not None and out < minimum:
        raise SchemaValidationError(field_name, f"must be >= {minimum}, got {out}")
    return out


def as_float(
    value: Any,
    field_name: str,
    *,
    default: float | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    if value is None:
        return default
    if isinstance(value, bool):
        raise SchemaValidationError(field_name, "expected a number, got bool")
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise SchemaValidationError(field_name, f"expected a number, got {value!r}") from exc
    if not math.isfinite(out):
        raise SchemaValidationError(field_name, "must be a finite number")
    if minimum is not None and out < minimum:
        raise SchemaValidationError(field_name, f"must be >= {minimum}, got {out}")
    if maximum is not None and out > maximum:
        raise SchemaValidationError(field_name, f"must be <= {maximum}, got {out}")
    return out


def as_bool(value: Any, field_name: str, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise SchemaValidationError(field_name, f"expected a boolean, got {type(value).__name__}")


def as_str_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raise SchemaValidationError(field_name, "expected a list of strings, got a bare string")
    if not isinstance(value, (list, tuple)):
        raise SchemaValidationError(field_name, "expected a list, got %s" % type(value).__name__)
    return [str(v) for v in value]


def as_float_map(value: Any, field_name: str) -> dict[str, float]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SchemaValidationError(field_name, "expected a mapping of numeric weights")
    out: dict[str, float] = {}
    for key, raw in value.items():
        out[str(key)] = as_float(raw, f"{field_name}.{key}", minimum=0.0)
    return out


def as_choice(
    value: Any, field_name: str, allowed: tuple[str, ...], *, default: str | None = None
) -> str | None:
    if value is None:
        return default
    text = str(value)
    if text not in allowed:
        raise SchemaValidationError(field_name, f"must be one of {list(allowed)}, got {text!r}")
    return text


@dataclass
class Dimensions:
    """Optional evaluation dimensions (all default to ``None`` = unspecified)."""

    language: str | None = None
    locale: str | None = None
    domain: str | None = None
    risk_category: str | None = None
    deployment_environment: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> Dimensions:
        data = _require_mapping(raw, "dimensions")
        return cls(
            language=as_str(data.get("language"), "dimensions.language"),
            locale=as_str(data.get("locale"), "dimensions.locale"),
            domain=as_str(data.get("domain"), "dimensions.domain"),
            risk_category=as_str(data.get("risk_category"), "dimensions.risk_category"),
            deployment_environment=as_str(
                data.get("deployment_environment"), "dimensions.deployment_environment"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in DIMENSION_KEYS}


@dataclass
class AdapterSpec:
    """How to reach the model/system under test."""

    kind: str = "mock"
    name: str = "mock"
    model_id: str = "synthetic/mock-oracle"
    revision: str | None = None
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> AdapterSpec:
        data = _require_mapping(raw, "adapter")
        kind = as_choice(data.get("kind"), "adapter.kind", ADAPTER_KINDS, default="mock")
        model_id = as_str(data.get("model_id"), "adapter.model_id", default="synthetic/mock-oracle")
        return cls(
            kind=kind or "mock",
            name=as_str(data.get("name"), "adapter.name", default=kind or "mock") or "mock",
            model_id=model_id or "synthetic/mock-oracle",
            revision=as_str(data.get("revision"), "adapter.revision"),
            params=_require_mapping(data.get("params"), "adapter.params"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "model_id": self.model_id,
            "revision": self.revision,
            "params": self.params,
        }


@dataclass
class PromptSpec:
    """Prompt protocol: which template, system prompt and few-shot pack to use."""

    prompt_id: str | None = None
    version: str | None = None
    system_prompt: str | None = None
    fewshot_path: str | None = None
    template: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> PromptSpec:
        data = _require_mapping(raw, "prompt")
        return cls(
            prompt_id=as_str(data.get("prompt_id"), "prompt.prompt_id"),
            version=as_str(data.get("version"), "prompt.version"),
            system_prompt=as_str(data.get("system_prompt"), "prompt.system_prompt", allow_empty=True),
            fewshot_path=as_str(data.get("fewshot_path"), "prompt.fewshot_path"),
            template=as_str(data.get("template"), "prompt.template", allow_empty=True),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "version": self.version,
            "system_prompt": self.system_prompt,
            "fewshot_path": self.fewshot_path,
            "template": self.template,
        }

    def template_payload(self) -> str:
        """Textual identity of this protocol, used for the prompt-template hash."""
        return "\n".join(
            [
                f"prompt_id={self.prompt_id or ''}",
                f"version={self.version or ''}",
                f"fewshot_path={self.fewshot_path or ''}",
                f"template={self.template or ''}",
                f"system_prompt={self.system_prompt or ''}",
            ]
        )


@dataclass
class TaskSpec:
    """Which task family and dataset slice to evaluate."""

    kind: str = "static_qa"
    path: str = "data/eval_set.jsonl"
    tasks: list[str] = field(default_factory=list)
    limit: int | None = None
    split: str | None = None
    episode_ids: list[str] = field(default_factory=list)
    perturbations: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> TaskSpec:
        data = _require_mapping(raw, "task")
        kind = as_choice(data.get("kind"), "task.kind", TASK_KINDS, default="static_qa")
        return cls(
            kind=kind or "static_qa",
            path=as_str(data.get("path"), "task.path", default="data/eval_set.jsonl")
            or "data/eval_set.jsonl",
            tasks=as_str_list(data.get("tasks"), "task.tasks"),
            limit=as_int(data.get("limit"), "task.limit", minimum=1),
            split=as_str(data.get("split"), "task.split"),
            episode_ids=as_str_list(data.get("episode_ids"), "task.episode_ids"),
            perturbations=as_str_list(data.get("perturbations"), "task.perturbations"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "path": self.path,
            "tasks": list(self.tasks),
            "limit": self.limit,
            "split": self.split,
            "episode_ids": list(self.episode_ids),
            "perturbations": list(self.perturbations),
        }


@dataclass
class DecodingSpec:
    """Decoding knobs that must be identical for two scores to be comparable."""

    seed: int = 0
    temperature: float = 0.0
    top_p: float = 1.0
    max_new_tokens: int = 256
    stop: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> DecodingSpec:
        data = _require_mapping(raw, "decoding")
        return cls(
            seed=_default(as_int(data.get("seed"), "decoding.seed", default=0, minimum=0), 0),
            temperature=_default(
                as_float(data.get("temperature"), "decoding.temperature", default=0.0, minimum=0.0),
                0.0,
            ),
            top_p=_default(
                as_float(data.get("top_p"), "decoding.top_p", default=1.0, minimum=0.0, maximum=1.0),
                1.0,
            ),
            max_new_tokens=_default(
                as_int(data.get("max_new_tokens"), "decoding.max_new_tokens", default=256, minimum=1),
                256,
            ),
            stop=as_str_list(data.get("stop"), "decoding.stop"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_new_tokens": self.max_new_tokens,
            "stop": list(self.stop),
        }

    @property
    def deterministic(self) -> bool:
        """Greedy decoding is deterministic; anything else is a sampled condition."""
        return self.temperature == 0.0


@dataclass
class RuntimeSpec:
    """Where and how the system ran (deployment-relevant metadata)."""

    device: str = "cpu"
    precision: str = "auto"
    quantization: str = "none"
    batch_size: int = 1
    timeout_s: float | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> RuntimeSpec:
        data = _require_mapping(raw, "runtime")
        return cls(
            device=as_str(data.get("device"), "runtime.device", default="cpu") or "cpu",
            precision=as_str(data.get("precision"), "runtime.precision", default="auto") or "auto",
            quantization=as_choice(
                data.get("quantization"), "runtime.quantization", QUANTIZATIONS, default="none"
            )
            or "none",
            batch_size=_default(
                as_int(data.get("batch_size"), "runtime.batch_size", default=1, minimum=1), 1
            ),
            timeout_s=as_float(data.get("timeout_s"), "runtime.timeout_s", minimum=0.0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "device": self.device,
            "precision": self.precision,
            "quantization": self.quantization,
            "batch_size": self.batch_size,
            "timeout_s": self.timeout_s,
        }


@dataclass
class EvaluatorSpec:
    """Which evaluators run, and how (rules vs judge adapter)."""

    quality: bool = True
    groundedness: bool = True
    safety: bool = True
    tool_use: bool = True
    cost_latency: bool = True
    judge_reliability: bool = False
    judge_mode: str = "rules"
    groundedness_overlap_threshold: float = 0.35
    safety_cases_path: str | None = None
    safety_taxonomy_path: str | None = None
    safety_category_weights: dict[str, float] = field(default_factory=dict)
    safety_severity_weights: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> EvaluatorSpec:
        data = _require_mapping(raw, "evaluators")
        return cls(
            quality=as_bool(data.get("quality"), "evaluators.quality", default=True),
            groundedness=as_bool(data.get("groundedness"), "evaluators.groundedness", default=True),
            safety=as_bool(data.get("safety"), "evaluators.safety", default=True),
            tool_use=as_bool(data.get("tool_use"), "evaluators.tool_use", default=True),
            cost_latency=as_bool(data.get("cost_latency"), "evaluators.cost_latency", default=True),
            judge_reliability=as_bool(
                data.get("judge_reliability"), "evaluators.judge_reliability", default=False
            ),
            judge_mode=as_choice(
                data.get("judge_mode"), "evaluators.judge_mode", JUDGE_MODES, default="rules"
            )
            or "rules",
            groundedness_overlap_threshold=_default(
                as_float(
                    data.get("groundedness_overlap_threshold"),
                    "evaluators.groundedness_overlap_threshold",
                    default=0.35,
                    minimum=0.0,
                    maximum=1.0,
                ),
                0.35,
            ),
            safety_cases_path=as_str(data.get("safety_cases_path"), "evaluators.safety_cases_path"),
            safety_taxonomy_path=as_str(
                data.get("safety_taxonomy_path"), "evaluators.safety_taxonomy_path"
            ),
            safety_category_weights=as_float_map(
                data.get("safety_category_weights"), "evaluators.safety_category_weights"
            ),
            safety_severity_weights=as_float_map(
                data.get("safety_severity_weights"), "evaluators.safety_severity_weights"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "quality": self.quality,
            "groundedness": self.groundedness,
            "safety": self.safety,
            "tool_use": self.tool_use,
            "cost_latency": self.cost_latency,
            "judge_reliability": self.judge_reliability,
            "judge_mode": self.judge_mode,
            "groundedness_overlap_threshold": self.groundedness_overlap_threshold,
            "safety_cases_path": self.safety_cases_path,
            "safety_taxonomy_path": self.safety_taxonomy_path,
            "safety_category_weights": dict(self.safety_category_weights),
            "safety_severity_weights": dict(self.safety_severity_weights),
        }


@dataclass
class MetricsSpec:
    """Bootstrap/statistics and decision-threshold configuration."""

    n_boot: int = 400
    alpha: float = 0.05
    seed: int = 0
    robust_capability_lambda: float = 1.0
    practical_effect_threshold: float = 0.02
    min_sample_size: int = 20

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> MetricsSpec:
        data = _require_mapping(raw, "metrics")
        return cls(
            n_boot=_default(
                as_int(data.get("n_boot"), "metrics.n_boot", default=400, minimum=10), 400
            ),
            alpha=_default(
                as_float(data.get("alpha"), "metrics.alpha", default=0.05, minimum=0.0, maximum=1.0),
                0.05,
            ),
            seed=_default(as_int(data.get("seed"), "metrics.seed", default=0, minimum=0), 0),
            robust_capability_lambda=_default(
                as_float(
                    data.get("robust_capability_lambda"),
                    "metrics.robust_capability_lambda",
                    default=1.0,
                    minimum=0.0,
                ),
                1.0,
            ),
            practical_effect_threshold=_default(
                as_float(
                    data.get("practical_effect_threshold"),
                    "metrics.practical_effect_threshold",
                    default=0.02,
                    minimum=0.0,
                ),
                0.02,
            ),
            min_sample_size=_default(
                as_int(data.get("min_sample_size"), "metrics.min_sample_size", default=20, minimum=1),
                20,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_boot": self.n_boot,
            "alpha": self.alpha,
            "seed": self.seed,
            "robust_capability_lambda": self.robust_capability_lambda,
            "practical_effect_threshold": self.practical_effect_threshold,
            "min_sample_size": self.min_sample_size,
        }


@dataclass
class ReportingSpec:
    """What gets written, how much raw content is retained, and how it is scrubbed."""

    output_dir: str = "runs"
    markdown: bool = True
    html: bool = True
    include_raw_outputs: bool = True
    pii_redaction: bool = True
    max_excerpt_chars: int = 400
    log_level: str = "info"

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> ReportingSpec:
        data = _require_mapping(raw, "reporting")
        level = as_str(data.get("log_level"), "reporting.log_level", default="info") or "info"
        if level not in ("debug", "info", "warning", "error"):
            raise SchemaValidationError(
                "reporting.log_level", f"must be one of ['debug','info','warning','error'], got {level!r}"
            )
        return cls(
            output_dir=as_str(data.get("output_dir"), "reporting.output_dir", default="runs") or "runs",
            markdown=as_bool(data.get("markdown"), "reporting.markdown", default=True),
            html=as_bool(data.get("html"), "reporting.html", default=True),
            include_raw_outputs=as_bool(
                data.get("include_raw_outputs"), "reporting.include_raw_outputs", default=True
            ),
            pii_redaction=as_bool(data.get("pii_redaction"), "reporting.pii_redaction", default=True),
            max_excerpt_chars=as_int(
                data.get("max_excerpt_chars"), "reporting.max_excerpt_chars", default=400, minimum=0
            )
            if data.get("max_excerpt_chars") is not None
            else 400,
            log_level=level,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_dir": self.output_dir,
            "markdown": self.markdown,
            "html": self.html,
            "include_raw_outputs": self.include_raw_outputs,
            "pii_redaction": self.pii_redaction,
            "max_excerpt_chars": self.max_excerpt_chars,
            "log_level": self.log_level,
        }


@dataclass
class GateRef:
    """Pointer to a release-gate spec plus the strictness policy."""

    path: str | None = None
    strict: bool = False

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> GateRef:
        data = _require_mapping(raw, "release_gates")
        return cls(
            path=as_str(data.get("path"), "release_gates.path"),
            strict=as_bool(data.get("strict"), "release_gates.strict", default=False),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "strict": self.strict}


@dataclass
class CostSpec:
    """Optional manual/provider-independent token prices for a deployment point."""

    input_per_million: float | None = None
    output_per_million: float | None = None
    currency: str = "USD"
    source: str = "manual configuration"

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> CostSpec:
        data = _require_mapping(raw, "cost")
        return cls(
            input_per_million=as_float(
                _first(data.get("input_per_million"), data.get("input_cost_per_million")),
                "cost.input_per_million", minimum=0.0,
            ),
            output_per_million=as_float(
                _first(data.get("output_per_million"), data.get("output_cost_per_million")),
                "cost.output_per_million", minimum=0.0,
            ),
            currency=as_str(data.get("currency"), "cost.currency", default="USD") or "USD",
            source=as_str(data.get("source"), "cost.source", default="manual configuration")
            or "manual configuration",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_per_million": self.input_per_million,
            "output_per_million": self.output_per_million,
            "currency": self.currency,
            "source": self.source,
        }


@dataclass
class RunSpec:
    """Fully specified, validated evaluation run.

    ``conditions`` records which experiment factors produced this run (empty for
    standalone runs). ``baseline_run`` is a path to a previous run directory used
    for paired comparison and regression classification.
    """

    run_name: str = "run"
    experiment_id: str | None = None
    parent_experiment_id: str | None = None
    tags: list[str] = field(default_factory=list)
    dimensions: Dimensions = field(default_factory=Dimensions)
    adapter: AdapterSpec = field(default_factory=AdapterSpec)
    prompt: PromptSpec = field(default_factory=PromptSpec)
    task: TaskSpec = field(default_factory=TaskSpec)
    decoding: DecodingSpec = field(default_factory=DecodingSpec)
    runtime: RuntimeSpec = field(default_factory=RuntimeSpec)
    evaluators: EvaluatorSpec = field(default_factory=EvaluatorSpec)
    metrics: MetricsSpec = field(default_factory=MetricsSpec)
    reporting: ReportingSpec = field(default_factory=ReportingSpec)
    gates: GateRef = field(default_factory=GateRef)
    cost: CostSpec = field(default_factory=CostSpec)
    baseline_run: str | None = None
    conditions: dict[str, Any] = field(default_factory=dict)
    evidence_class: str = "MEASURED"

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> RunSpec:
        data = dict(_require_mapping(raw, "run_spec"))
        # Allow both ``run: {...}`` (nested) and a flat spec at the top level.
        if isinstance(data.get("run"), dict):
            run_block = dict(data.pop("run"))
            run_block.update({k: v for k, v in data.items() if k not in run_block})
            data = run_block
        return cls(
            run_name=as_str(data.get("name") or data.get("run_name"), "run.name", default="run")
            or "run",
            experiment_id=as_str(data.get("experiment_id"), "run.experiment_id"),
            parent_experiment_id=as_str(
                data.get("parent_experiment_id"), "run.parent_experiment_id"
            ),
            tags=as_str_list(data.get("tags"), "run.tags"),
            dimensions=Dimensions.from_dict(data.get("dimensions")),
            adapter=AdapterSpec.from_dict(data.get("adapter")),
            prompt=PromptSpec.from_dict(data.get("prompt")),
            task=TaskSpec.from_dict(data.get("task")),
            decoding=DecodingSpec.from_dict(data.get("decoding")),
            runtime=RuntimeSpec.from_dict(data.get("runtime")),
            evaluators=EvaluatorSpec.from_dict(data.get("evaluators")),
            metrics=MetricsSpec.from_dict(data.get("metrics")),
            reporting=ReportingSpec.from_dict(data.get("reporting")),
            gates=GateRef.from_dict(data.get("release_gates")),
            cost=CostSpec.from_dict(data.get("cost")),
            baseline_run=as_str(data.get("baseline_run"), "run.baseline_run"),
            conditions={
                str(k): v for k, v in _require_mapping(data.get("conditions"), "run.conditions").items()
            },
            evidence_class=as_choice(
                data.get("evidence_class"),
                "run.evidence_class",
                ("MEASURED", "MOCK", "DEMONSTRATION", "HUMAN_VALIDATED", "PROJECT_METRIC"),
                default="MEASURED",
            )
            or "MEASURED",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_name": self.run_name,
            "experiment_id": self.experiment_id,
            "parent_experiment_id": self.parent_experiment_id,
            "tags": list(self.tags),
            "dimensions": self.dimensions.to_dict(),
            "adapter": self.adapter.to_dict(),
            "prompt": self.prompt.to_dict(),
            "task": self.task.to_dict(),
            "decoding": self.decoding.to_dict(),
            "runtime": self.runtime.to_dict(),
            "evaluators": self.evaluators.to_dict(),
            "metrics": self.metrics.to_dict(),
            "reporting": self.reporting.to_dict(),
            "release_gates": self.gates.to_dict(),
            "cost": self.cost.to_dict(),
            "baseline_run": self.baseline_run,
            "conditions": dict(self.conditions),
            "evidence_class": self.evidence_class,
        }

    def semantic_dict(self) -> dict[str, Any]:
        """The part of the spec that defines *what* was measured (hash input).

        Credentials are deliberately excluded from the semantic identity. They
        affect transport, not the evaluation question, and retaining them in a
        hash would make a secret rotation look like a benchmark condition.
        The in-memory spec remains unchanged; artifact writers redact it before
        persistence.
        """
        from apertus_eval_prep.utils.pii import redact_for_artifact

        payload = {k: v for k, v in self.to_dict().items() if k not in VOLATILE_CONFIG_KEYS}
        return redact_for_artifact(payload)

    def config_hash(self) -> str:
        """Stable 16-hex identity of the evaluation semantics."""
        return hash_config(self.semantic_dict())

    def with_conditions(self, conditions: dict[str, Any]) -> RunSpec:
        """Return a copy carrying experiment-factor labels (used by the matrix)."""
        clone = RunSpec.from_dict(self.to_dict())
        clone.conditions = {str(k): v for k, v in conditions.items()}
        return clone


@dataclass
class ComparisonSpec:
    """Decision thresholds for baseline-vs-candidate classification."""

    practical_effect_threshold: float = 0.02
    min_sample_size: int = 20
    safety_critical: bool = False
    robust_capability_lambda: float = 1.0
    n_boot: int = 400
    alpha: float = 0.05
    seed: int = 0

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> ComparisonSpec:
        data = _require_mapping(raw, "comparison")
        return cls(
            practical_effect_threshold=_default(
                as_float(
                    data.get("practical_effect_threshold"),
                    "comparison.practical_effect_threshold",
                    default=0.02,
                    minimum=0.0,
                ),
                0.02,
            ),
            min_sample_size=_default(
                as_int(data.get("min_sample_size"), "comparison.min_sample_size", default=20, minimum=1),
                20,
            ),
            safety_critical=as_bool(
                data.get("safety_critical"), "comparison.safety_critical", default=False
            ),
            robust_capability_lambda=_default(
                as_float(
                    data.get("robust_capability_lambda", data.get("lambda")),
                    "comparison.robust_capability_lambda",
                    default=1.0,
                    minimum=0.0,
                ),
                1.0,
            ),
            n_boot=_default(
                as_int(data.get("n_boot"), "comparison.n_boot", default=400, minimum=10), 400
            ),
            alpha=_default(
                as_float(data.get("alpha"), "comparison.alpha", default=0.05, minimum=0.0, maximum=1.0),
                0.05,
            ),
            seed=_default(as_int(data.get("seed"), "comparison.seed", default=0, minimum=0), 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "practical_effect_threshold": self.practical_effect_threshold,
            "min_sample_size": self.min_sample_size,
            "safety_critical": self.safety_critical,
            "robust_capability_lambda": self.robust_capability_lambda,
            "n_boot": self.n_boot,
            "alpha": self.alpha,
            "seed": self.seed,
        }


@dataclass
class ExperimentSpec:
    """Declarative evaluation matrix: one baseline plus factor combinations.

    ``base`` is the raw run-spec mapping shared by every cell; ``baseline`` holds
    the factor levels that define the reference condition; ``factors`` maps factor
    names (or dotted spec paths) to the levels to vary.
    """

    name: str = "experiment"
    experiment_id: str = "experiment"
    base: dict[str, Any] = field(default_factory=dict)
    baseline: dict[str, Any] = field(default_factory=dict)
    factors: dict[str, list[Any]] = field(default_factory=dict)
    max_runs: int = 64
    comparison: ComparisonSpec = field(default_factory=ComparisonSpec)
    notes: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> ExperimentSpec:
        data = dict(_require_mapping(raw, "experiment_spec"))
        exp_block = data.get("experiment")
        if isinstance(exp_block, dict):
            merged = dict(data)
            merged.pop("experiment")
            merged.update(exp_block)
            data = merged
        factors_raw = _require_mapping(data.get("factors"), "experiment.factors")
        factors: dict[str, list[Any]] = {}
        for key, levels in factors_raw.items():
            if not isinstance(levels, (list, tuple)) or not levels:
                raise SchemaValidationError(
                    f"experiment.factors.{key}", "must be a non-empty list of levels"
                )
            factors[str(key)] = list(levels)
        base = _require_mapping(data.get("base"), "experiment.base")
        if not base:
            raise SchemaValidationError("experiment.base", "is required (the shared run spec)")
        return cls(
            name=as_str(data.get("name"), "experiment.name", default="experiment") or "experiment",
            experiment_id=as_str(data.get("id") or data.get("experiment_id"), "experiment.id", default="experiment")
            or "experiment",
            base=base,
            baseline=_require_mapping(data.get("baseline"), "experiment.baseline"),
            factors=factors,
            max_runs=as_int(data.get("max_runs"), "experiment.max_runs", default=64, minimum=1) or 64,
            comparison=ComparisonSpec.from_dict(data.get("comparison")),
            notes=as_str(data.get("notes"), "experiment.notes", allow_empty=True),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "experiment_id": self.experiment_id,
            "base": self.base,
            "baseline": self.baseline,
            "factors": {k: list(v) for k, v in self.factors.items()},
            "max_runs": self.max_runs,
            "comparison": self.comparison.to_dict(),
            "notes": self.notes,
        }
