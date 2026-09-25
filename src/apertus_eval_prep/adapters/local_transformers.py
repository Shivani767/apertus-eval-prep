"""Optional, lazy local Transformers adapter for open-weight causal models."""
from __future__ import annotations

import time
from typing import Any

from apertus_eval_prep.adapters.base import (
    AdapterCapabilities, AdapterResponse, CompletionRequest, ModelAdapter, Usage,
)
from apertus_eval_prep.core.errors import (
    AdapterError, AdapterGenerationError, AdapterMalformedOutputError, AdapterModelLoadError,
    AdapterOOMError, AdapterResponseError, AdapterTimeoutError,
)
from apertus_eval_prep.utils.runtime_profile import profile_runtime

_ALLOWED_DEVICES = {"auto", "cpu", "cuda"}
_ALLOWED_DTYPES = {"auto", "float32", "float16", "bfloat16"}
_ALLOWED_QUANTIZATIONS = {"none", "int8", "int4"}


class LocalTransformersAdapter(ModelAdapter):
    """Small local generation adapter; optional packages load only on first use."""

    kind = "local_transformers"

    @classmethod
    def from_params(cls, params: dict[str, Any], *, name: str, model_id: str,
                    revision: str | None, seed: int) -> "LocalTransformersAdapter":
        return cls(name=name, model_id=model_id, revision=revision, seed=seed,
                   params=dict(params or {}))

    def __init__(self, *, name: str, model_id: str, revision: str | None = None,
                 seed: int = 0, params: dict[str, Any] | None = None) -> None:
        if not str(model_id or "").strip():
            raise AdapterModelLoadError(
                "local Transformers adapter requires a non-empty model_id", adapter=name
            )
        super().__init__(
            name=name, model_id=model_id, revision=revision, seed=seed,
            capabilities=AdapterCapabilities(
                supports_tools=False, supports_seed=True,
                reports_usage=True, deterministic=False,
            ),
        )
        self.params = dict(params or {})
        self.device = str(self.params.get("device", "auto")).lower()
        self.dtype = str(self.params.get("dtype", self.params.get("precision", "auto"))).lower()
        self.quantization = str(self.params.get("quantization", "none")).lower()
        if self.device not in _ALLOWED_DEVICES:
            raise AdapterResponseError(f"unsupported local device: {self.device!r}")
        if self.dtype not in _ALLOWED_DTYPES:
            raise AdapterResponseError(f"unsupported local dtype: {self.dtype!r}")
        if self.quantization not in _ALLOWED_QUANTIZATIONS:
            raise AdapterResponseError(f"unsupported local quantization: {self.quantization!r}")
        max_new_tokens = int(self.params.get("max_new_tokens", 256))
        temperature = float(self.params.get("temperature", 0.0))
        top_p = float(self.params.get("top_p", 1.0))
        do_sample = self.params.get("do_sample", temperature > 0)
        trust_remote_code = self.params.get("trust_remote_code", False)
        timeout_s = self.params.get("timeout_s")
        if max_new_tokens < 1 or not 0.0 <= temperature <= 2.0 or not 0.0 < top_p <= 1.0:
            raise AdapterResponseError("invalid local generation settings", adapter=name)
        if not isinstance(do_sample, bool) or not isinstance(trust_remote_code, bool):
            raise AdapterResponseError("local boolean settings must be booleans", adapter=name)
        if timeout_s is not None and (float(timeout_s) < 0.0):
            raise AdapterResponseError("timeout_s must be non-negative", adapter=name)
        self._model = None
        self._tokenizer = None
        self._torch = None
        self._profile: dict[str, Any] | None = None
        self._loaded_device: str | None = None

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise AdapterModelLoadError(
                "local Transformers evaluation requires optional dependencies; "
                "install the 'real-model' extra or use the offline mock adapter",
                adapter=self.name,
            ) from exc
        tokenizer_id = str(self.params.get("tokenizer_id") or self.model_id)
        tokenizer_revision = self.params.get("tokenizer_revision", self.revision)
        trust_remote_code = bool(self.params.get("trust_remote_code", False))
        try:
            self._torch = torch
            torch.manual_seed(self.seed)
            device = self.device
            if device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype_name = self.dtype
            if dtype_name == "auto":
                dtype_name = "float16" if device == "cuda" else "float32"
            dtype = getattr(torch, dtype_name)
            self._tokenizer = AutoTokenizer.from_pretrained(
                tokenizer_id, revision=tokenizer_revision, trust_remote_code=trust_remote_code,
            )
            load_kwargs: dict[str, Any] = {
                "revision": self.revision, "trust_remote_code": trust_remote_code,
                "torch_dtype": dtype,
            }
            if self.quantization != "none":
                try:
                    from transformers import BitsAndBytesConfig
                except ImportError as exc:
                    raise AdapterModelLoadError(
                        "local quantization requires optional Transformers/BitsAndBytes support",
                        adapter=self.name,
                    ) from exc
                load_kwargs["quantization_config"] = (
                    BitsAndBytesConfig(load_in_8bit=True) if self.quantization == "int8"
                    else BitsAndBytesConfig(load_in_4bit=True)
                )
            self._model = AutoModelForCausalLM.from_pretrained(self.model_id, **load_kwargs)
            if self.quantization == "none":
                self._model.to(device)
            self._model.eval()
            self._loaded_device = device
            self._profile = profile_runtime(
                device=device, precision=self.dtype, quantization=self.quantization,
                include_torch=True,
            )
            self._profile["tokenizer_id"] = tokenizer_id
            self._profile["tokenizer_revision"] = tokenizer_revision
        except (AdapterModelLoadError, AdapterResponseError, AdapterOOMError, AdapterTimeoutError):
            raise
        except Exception as exc:
            if "out of memory" in str(exc).lower():
                raise AdapterOOMError("local model exhausted available memory", adapter=self.name) from exc
            raise AdapterModelLoadError("local model/tokenizer could not be loaded", adapter=self.name) from exc

    @staticmethod
    def _token_count(value: Any) -> int:
        try:
            return int(value.numel()) if hasattr(value, "numel") else len(value)
        except (TypeError, AttributeError):
            return 0

    def complete(self, request: CompletionRequest) -> AdapterResponse:
        started = time.perf_counter()
        self._load()
        assert self._torch is not None and self._tokenizer is not None and self._model is not None
        try:
            prompt = f"{request.system_prompt}\n\n{request.prompt}" if request.system_prompt else request.prompt
            inputs = self._tokenizer(prompt, return_tensors="pt")
            try:
                device = next(self._model.parameters()).device
            except (StopIteration, AttributeError):
                device = self._torch.device(self._loaded_device or "cpu")
            inputs = {key: value.to(device) for key, value in inputs.items()}
            do_sample = bool(self.params.get("do_sample", request.temperature > 0))
            kwargs: dict[str, Any] = {
                **inputs,
                "max_new_tokens": int(self.params.get("max_new_tokens", request.max_new_tokens)),
                "do_sample": do_sample,
                "top_p": float(request.top_p),
            }
            if do_sample:
                kwargs["temperature"] = max(float(request.temperature), 1e-5)
            output_ids = self._model.generate(**kwargs)
            if output_ids is None or self._token_count(output_ids) == 0:
                raise AdapterMalformedOutputError("local model returned no generated sequence", adapter=self.name)
            first = output_ids[0]
            prompt_length = int(inputs["input_ids"].shape[-1])
            generated = first[prompt_length:]
            text = self._tokenizer.decode(generated, skip_special_tokens=True)
            if not isinstance(text, str):
                raise AdapterMalformedOutputError("local tokenizer returned non-text output", adapter=self.name)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            timeout_s = self.params.get("timeout_s")
            if timeout_s is not None and elapsed_ms > float(timeout_s) * 1000.0:
                raise AdapterTimeoutError("local generation exceeded configured timeout", adapter=self.name)
            input_count = self._token_count(inputs["input_ids"])
            output_count = self._token_count(generated)
            return AdapterResponse(
                text=text,
                usage=Usage(input_tokens=input_count, output_tokens=output_count,
                            total_tokens=input_count + output_count),
                latency_ms=elapsed_ms, finish_reason="stop", simulated=False,
                raw={"runtime_profile": self._profile, "client_side_wall_clock": True,
                     "device": self._loaded_device, "dtype": self.dtype,
                     "quantization": self.quantization},
            )
        except (AdapterError, AdapterTimeoutError):
            raise
        except Exception as exc:
            if "out of memory" in str(exc).lower():
                raise AdapterOOMError("local generation exhausted available memory", adapter=self.name) from exc
            raise AdapterGenerationError("local model generation failed", adapter=self.name) from exc

    def describe(self) -> dict[str, Any]:
        payload = super().describe()
        payload.update({
            "device": self.device,
            "dtype": self.dtype,
            "quantization": self.quantization,
            "tokenizer_id": self.params.get("tokenizer_id", self.model_id),
            "tokenizer_revision": self.params.get("tokenizer_revision", self.revision),
            "trust_remote_code": bool(self.params.get("trust_remote_code", False)),
            "runtime_profile": self._profile,
        })
        return payload


LocalAdapter = LocalTransformersAdapter
__all__ = ["LocalTransformersAdapter", "LocalAdapter"]
