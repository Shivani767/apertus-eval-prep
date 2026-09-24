"""Deterministic offline mock adapter.

This adapter exists to exercise the *platform* — statistics, pipelines, gates,
reporting, CI — without internet, API keys, GPUs, or paid models.

Honesty rules enforced here:

* every response carries ``simulated=True`` and the adapter reports
  ``evidence_class == "MOCK"``;
* scores produced through it are labelled synthetic in metrics, reports and the
  run manifest, and must never be presented as model benchmark results;
* behaviour is a pure function of (prompt, example id, seed, conditions), so the
  same input always yields the same output and the same "accuracy".

The optional oracle (expected answers supplied by the task layer) lets a study
configure a *skill profile* — an accuracy target and sensitivity to temperature,
prompt, backend and quantization — which is exactly what the Variance Lab needs
to be testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apertus_eval_prep.adapters.base import (
    AdapterCapabilities,
    AdapterResponse,
    CompletionRequest,
    ModelAdapter,
    ToolCall,
    Usage,
    estimate_tokens,
)
from apertus_eval_prep.core.errors import AdapterError, AdapterResponseError, AdapterTimeoutError
from apertus_eval_prep.utils.hashing import stable_hash

MOCK_MODES: tuple[str, ...] = (
    "normal",
    "structured",
    "invalid",
    "malformed",
    "timeout",
    "error",
    "refusal",
    "tool_call",
    "flaky",
)

_LETTERS = ("A", "B", "C", "D")
_REFUSAL_TEXT = "I'm sorry, but I can't help with that request."
_DEFAULT_TEXT = "This is a synthetic mock answer used for offline pipeline testing."
_INVALID_TEXT = "???"
_MISSING_ORACLE = "[mock: no oracle answer configured]"

#: Rough per-token decode cost used to fabricate plausible latency in mock runs.
_MS_PER_TOKEN = 1.5


def deterministic_unit(key: str) -> float:
    """Deterministic pseudo-random value in [0, 1) derived from ``key``."""
    return int(stable_hash(key, length=16), 16) / float(16**16)


@dataclass
class MockSkillProfile:
    """Synthetic capability profile of the mock "model".

    All probabilities are per-example and applied with a deterministic roll, so
    the same configuration always produces the same accuracy.
    """

    skill: float = 0.78
    unsafe_rate: float = 0.08
    false_refusal_rate: float = 0.05
    invalid_rate: float = 0.0
    seed_jitter: float = 0.04
    temperature_penalty: float = 0.05
    prompt_penalties: dict[str, float] = field(default_factory=dict)
    backend_penalties: dict[str, float] = field(default_factory=dict)
    quantization_penalties: dict[str, float] = field(default_factory=dict)
    latency_base_ms: float = 35.0
    latency_jitter_ms: float = 25.0
    simulate_latency: bool = True
    report_usage: bool = True
    fail_rate: float = 0.2

    @classmethod
    def from_params(cls, params: dict[str, Any] | None) -> MockSkillProfile:
        params = dict(params or {})
        known = {f for f in cls.__dataclass_fields__}
        unknown = sorted(set(params) - known)
        if unknown:
            raise AdapterResponseError(
                f"unknown mock adapter params: {unknown}; known params are {sorted(known)}"
            )
        return cls(**params)

    def condition_penalty(self, conditions: dict[str, Any]) -> float:
        """Total accuracy penalty for the conditions this request ran under."""
        penalty = 0.0
        if float(conditions.get("temperature") or 0.0) > 0.0:
            penalty += self.temperature_penalty
        prompt_key = (
            conditions.get("prompt_template")
            or conditions.get("prompt_version")
            or conditions.get("prompt_id")
        )
        if prompt_key is not None:
            penalty += self.prompt_penalties.get(str(prompt_key), 0.0)
        backend = conditions.get("backend")
        if backend is not None:
            penalty += self.backend_penalties.get(str(backend), 0.0)
        quantization = conditions.get("quantization")
        if quantization is not None:
            penalty += self.quantization_penalties.get(str(quantization), 0.0)
        return penalty

    def probability_of_success(self, conditions: dict[str, Any], seed: int) -> float:
        """Success probability for one example under one condition."""
        offset = (deterministic_unit(f"seed-offset:{seed}") - 0.5) * 2.0 * self.seed_jitter
        return min(1.0, max(0.0, self.skill - self.condition_penalty(conditions) + offset))


class MockAdapter(ModelAdapter):
    """Deterministic offline adapter (see module docstring for honesty rules)."""

    kind = "mock"

    def __init__(
        self,
        *,
        name: str = "mock-oracle",
        model_id: str = "synthetic/mock-oracle-v1",
        revision: str | None = "fixture-v1",
        seed: int = 0,
        mode: str = "normal",
        profile: MockSkillProfile | None = None,
        oracle: dict[str, str] | None = None,
    ) -> None:
        if mode not in MOCK_MODES:
            raise AdapterResponseError(f"mode must be one of {list(MOCK_MODES)}, got {mode!r}")
        super().__init__(
            name=name,
            model_id=model_id,
            revision=revision,
            seed=seed,
            capabilities=AdapterCapabilities(
                supports_tools=True,
                supports_system_prompt=True,
                supports_seed=True,
                reports_usage=True,
                deterministic=True,
                runs_locally=True,
            ),
        )
        self.mode = mode
        self.profile = profile or MockSkillProfile()
        self.oracle: dict[str, str] = dict(oracle or {})

    # -- configuration ---------------------------------------------------
    @classmethod
    def from_params(
        cls,
        params: dict[str, Any] | None,
        *,
        name: str = "mock-oracle",
        model_id: str = "synthetic/mock-oracle-v1",
        revision: str | None = "fixture-v1",
        seed: int = 0,
    ) -> MockAdapter:
        params = dict(params or {})
        mode = str(params.pop("mode", "normal"))
        oracle_source = params.pop("oracle_source", None)
        if oracle_source not in (None, "dataset_gold", "none"):
            raise AdapterResponseError(
                "adapter.params.oracle_source must be 'dataset_gold' or 'none', "
                f"got {oracle_source!r}"
            )
        profile = MockSkillProfile.from_params(params)
        return cls(
            name=name,
            model_id=model_id,
            revision=revision,
            seed=seed,
            mode=mode,
            profile=profile,
            oracle=None,
        )

    @property
    def evidence_class(self) -> str:
        return "MOCK"

    def set_oracle(self, mapping: dict[str, str]) -> None:
        """Supply expected answers (task layer only; documented as synthetic)."""
        self.oracle = {str(k): str(v) for k, v in mapping.items()}

    # -- behaviour -------------------------------------------------------
    def _key(self, request: CompletionRequest) -> str:
        example = request.example_id or stable_hash(request.prompt, length=12)
        return f"{example}|step{request.step}"

    def _variant(self, request: CompletionRequest) -> str:
        seed = int(dict(request.conditions).get("seed", request.seed) or 0)
        return stable_hash(
            {"key": self._key(request), "seed": seed, "conditions": dict(request.conditions)},
            length=8,
        )

    def _default_text(self, request: CompletionRequest) -> str:
        return f"{_DEFAULT_TEXT} [mock-variant:{self._variant(request)}]"

    def _simulated_latency(self, request: CompletionRequest, output_tokens: int) -> float:
        if not self.profile.simulate_latency:
            return 0.0
        jitter = deterministic_unit(f"latency:{self._key(request)}") * self.profile.latency_jitter_ms
        return round(
            self.profile.latency_base_ms + jitter + output_tokens * _MS_PER_TOKEN,
            3,
        )

    def _usage(self, request: CompletionRequest, text: str) -> Usage | None:
        if not self.profile.report_usage:
            return None
        prompt_tokens = estimate_tokens(request.prompt) + estimate_tokens(request.system_prompt or "")
        output_tokens = estimate_tokens(text)
        return Usage(
            input_tokens=prompt_tokens,
            output_tokens=output_tokens,
            total_tokens=prompt_tokens + output_tokens,
        )

    def complete(self, request: CompletionRequest) -> AdapterResponse:
        """Produce a deterministic response, or raise the configured failure."""
        conditions = dict(request.conditions)
        seed = int(conditions.get("seed", request.seed) or 0)
        roll = deterministic_unit(f"roll:{self._key(request)}|{seed}|{stable_hash(conditions, length=8)}")

        if self.mode == "timeout" or (self.mode == "flaky" and roll < self.profile.fail_rate):
            latency = self._simulated_latency(request, 0) or 50.0
            raise AdapterTimeoutError(
                f"simulated timeout after {latency:.1f} ms",
                adapter=self.name,
                example_id=request.example_id,
            )
        if self.mode == "error":
            raise AdapterError("simulated adapter error", adapter=self.name, example_id=request.example_id)

        success_probability = self.profile.probability_of_success(conditions, seed)
        if request.tools and self.mode in ("tool_call", "normal"):
            plan = self._tool_plan(request)
            if plan or (self.mode == "tool_call" and request.step == 0):
                response = self._tool_response(request, roll, success_probability)
                if response is not None:
                    return response

        text = self._compose_text(request, roll, success_probability)
        latency = self._simulated_latency(request, estimate_tokens(text))
        return AdapterResponse(
            text=text,
            usage=self._usage(request, text),
            latency_ms=latency,
            finish_reason="stop",
            simulated=True,
            seed=seed,
            variant=stable_hash({"key": self._key(request), "seed": seed, "conditions": conditions}, length=8),
        )

    # -- response composition -------------------------------------------
    def _tool_plan(self, request: CompletionRequest) -> list[dict[str, Any]]:
        plan = request.metadata.get("tool_plan") or []
        if not isinstance(plan, list):
            raise AdapterResponseError("metadata.tool_plan must be a list of {name, arguments}")
        return [step for step in plan if isinstance(step, dict)]

    def _tool_response(
        self, request: CompletionRequest, roll: float, success_probability: float
    ) -> AdapterResponse | None:
        """Emit the next planned tool call, or ``None`` when the plan is exhausted."""
        conditions = dict(request.conditions)
        seed = int(conditions.get("seed", request.seed) or 0)
        plan = self._tool_plan(request)
        step = request.step
        if not plan and self.mode == "tool_call" and request.step == 0 and request.tools:
            plan = [{"name": request.tools[0].name, "arguments": {}}]
        if step >= len(plan):
            return None
        entry = plan[step]
        name = str(entry.get("name") or "")
        arguments = dict(entry.get("arguments") or {})
        if not name:
            raise AdapterResponseError(f"tool_plan step {step} has no tool name")
        if request.tools and name not in {t.name for t in request.tools}:
            raise AdapterResponseError(
                f"tool_plan requests unavailable tool {name!r}; available: "
                f"{sorted(t.name for t in request.tools)}"
            )
        # Deterministic schema-failure injection: a configured rate of calls is
        # emitted with arguments missing a required key.
        inject = deterministic_unit(f"inject:{self._key(request)}") < max(
            0.0, 1.0 - success_probability
        ) if request.metadata.get("inject_tool_schema_error") else False
        if inject:
            arguments = {}
        call = ToolCall(name=name, arguments=arguments, call_id=f"{self._key(request)}-{name}")
        latency = self._simulated_latency(request, 0) or 25.0
        return AdapterResponse(
            text="",
            tool_calls=[call],
            usage=self._usage(request, ""),
            latency_ms=latency,
            finish_reason="tool_call",
            simulated=True,
            seed=int(conditions.get("seed", request.seed) or 0),
            variant=stable_hash({"key": self._key(request), "seed": seed, "conditions": conditions}, length=8),
        )

    def _oracle_answer(self, request: CompletionRequest) -> str | None:
        answer = request.metadata.get("oracle_answer")
        if isinstance(answer, str) and answer:
            return answer
        if request.example_id is not None:
            return self.oracle.get(str(request.example_id))
        return None

    def _distractor(self, request: CompletionRequest, gold: str) -> str:
        """A deterministic wrong-but-plausible answer (never the correct one)."""
        fmt = request.metadata.get("answer_format", "text")
        if fmt == "letter":
            options = [L for L in _LETTERS if L != gold.upper()]
            return options[int(deterministic_unit(f"wrong:{self._key(request)}") * len(options))]
        if fmt == "number":
            try:
                value = int(float(gold))
            except (TypeError, ValueError):
                value = 0
            offset = 1 + int(deterministic_unit(f"wrong:{self._key(request)}") * 3)
            return str(value - offset)
        if fmt == "label":
            return "UNSUPPORTED" if gold.upper() != "UNSUPPORTED" else "SUPPORTED"
        reason = request.metadata.get("wrong_answer_text")
        return str(reason) if reason else _DEFAULT_TEXT

    def _compose_text(
        self, request: CompletionRequest, roll: float, success_probability: float
    ) -> str:
        """Answer text for the current mode/expectation."""
        if self.mode in ("invalid", "malformed"):
            return _INVALID_TEXT
        if self.mode == "refusal":
            return _REFUSAL_TEXT

        expectation = request.metadata.get("expectation")
        if expectation in ("refuse", "redirect"):
            unsafe = deterministic_unit(f"unsafe:{self._key(request)}") < self.profile.unsafe_rate
            if unsafe:
                return str(request.metadata.get("compliance_text") or _DEFAULT_TEXT)
            return str(
                request.metadata.get("safe_text")
                or request.metadata.get("refusal_text")
                or _REFUSAL_TEXT
            )
        if expectation == "answer":
            false_refusal = (
                deterministic_unit(f"benign:{self._key(request)}")
                < self.profile.false_refusal_rate
            )
            if false_refusal:
                return _REFUSAL_TEXT
            answer = self._oracle_answer(request)
            if answer is not None:
                return answer
            return str(request.metadata.get("benign_answer") or _DEFAULT_TEXT)

        oracle = self._oracle_answer(request)
        if oracle is None:
            return self._default_text(request)
        if roll < success_probability:
            return self._format_answer(request, oracle)
        if (
            self.profile.invalid_rate > 0.0
            and deterministic_unit(f"invalid:{self._key(request)}") < self.profile.invalid_rate
        ):
            return _INVALID_TEXT
        return self._distractor(request, oracle)

    def _format_answer(self, request: CompletionRequest, answer: str) -> str:
        fmt = request.metadata.get("answer_format", "text")
        if fmt == "letter":
            return answer.strip().upper()
        if fmt in ("number", "label", "refuse", "text"):
            result = answer if fmt == "text" else f"{answer.strip()}"
            expected_sources = request.metadata.get("expected_sources") or request.metadata.get("expected_source_ids") or []
            citations = " ".join(f"[{str(source)}]" for source in expected_sources)
            return f"{result} {citations}".strip() if citations else result
        return answer
