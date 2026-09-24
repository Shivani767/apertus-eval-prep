"""Lazy local transformers adapter; model weights are never loaded at import time."""
from __future__ import annotations

from typing import Any

from apertus_eval_prep.adapters.base import AdapterCapabilities, AdapterResponse, CompletionRequest, ModelAdapter, Usage, estimate_tokens
from apertus_eval_prep.core.errors import AdapterError, AdapterResponseError


class LocalAdapter(ModelAdapter):
    kind = "local"

    @classmethod
    def from_params(cls, params: dict[str, Any], *, name: str, model_id: str,
                    revision: str | None, seed: int) -> "LocalAdapter":
        return cls(name=name, model_id=model_id, revision=revision, seed=seed,
                   params=dict(params or {}))

    def __init__(self, *, name: str, model_id: str, revision: str | None = None,
                 seed: int = 0, params: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, model_id=model_id, revision=revision, seed=seed,
                         capabilities=AdapterCapabilities(supports_tools=False, supports_seed=True, reports_usage=True))
        self.params = dict(params or {})
        self._model = None
        self._tokenizer = None

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_id, revision=self.revision)
            self._model = AutoModelForCausalLM.from_pretrained(self.model_id, revision=self.revision)
            self._model.eval()
        except Exception as exc:
            raise AdapterError("local model could not be loaded", adapter=self.name) from exc

    def complete(self, request: CompletionRequest) -> AdapterResponse:
        self._load()
        assert self._tokenizer is not None and self._model is not None
        inputs = self._tokenizer(request.prompt, return_tensors="pt")
        outputs = self._model.generate(**inputs, max_new_tokens=request.max_new_tokens,
                                       do_sample=request.temperature > 0,
                                       temperature=max(request.temperature, 1e-5),
                                       top_p=request.top_p)
        text = self._tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        return AdapterResponse(text=text, usage=Usage(input_tokens=estimate_tokens(request.prompt), output_tokens=estimate_tokens(text)), simulated=False)


__all__ = ["LocalAdapter"]
