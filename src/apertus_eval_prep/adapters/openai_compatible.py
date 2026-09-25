"""Provider-neutral OpenAI-compatible HTTP adapter.

No provider URL or price is embedded.  The caller must configure ``base_url``;
credentials are read from an environment variable and never returned/logged.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from apertus_eval_prep.adapters.base import AdapterCapabilities, AdapterResponse, CompletionRequest, ModelAdapter, Usage
from apertus_eval_prep.core.errors import AdapterError, AdapterResponseError


class OpenAICompatibleAdapter(ModelAdapter):
    kind = "openai_compatible"

    @classmethod
    def from_params(cls, params: dict[str, Any], *, name: str, model_id: str,
                    revision: str | None, seed: int) -> "OpenAICompatibleAdapter":
        return cls(name=name, model_id=model_id, revision=revision, seed=seed,
                   params=dict(params or {}))

    def __init__(self, *, name: str, model_id: str, revision: str | None = None,
                 seed: int = 0, params: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, model_id=model_id, revision=revision, seed=seed,
                         capabilities=AdapterCapabilities(supports_tools=True, supports_seed=True, reports_usage=True, deterministic=False, runs_locally=False))
        self.params = dict(params or {})
        if not self.params.get("base_url"):
            raise AdapterError("openai_compatible adapter requires an explicit base_url")

    def complete(self, request: CompletionRequest) -> AdapterResponse:
        base_url = str(self.params["base_url"]).rstrip("/")
        token = os.environ.get(str(self.params.get("api_key_env", "OPENAI_API_KEY")))
        payload: dict[str, Any] = {"model": self.model_id, "messages": [{"role": "user", "content": request.prompt}],
                                   "temperature": request.temperature, "top_p": request.top_p, "max_tokens": request.max_new_tokens}
        if request.system_prompt:
            payload["messages"].insert(0, {"role": "system", "content": request.system_prompt})
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(f"{base_url}/chat/completions", data=json.dumps(payload).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=float(self.params.get("timeout_s", 30.0))) as response:
                body = json.loads(response.read().decode())
        except Exception as exc:
            raise AdapterError("OpenAI-compatible request failed", adapter=self.name) from exc
        try:
            choice = body["choices"][0]["message"]
            return AdapterResponse(text=str(choice.get("content") or ""), usage=None, simulated=False)
        except (KeyError, IndexError, TypeError) as exc:
            raise AdapterResponseError("OpenAI-compatible response shape is invalid") from exc


__all__ = ["OpenAICompatibleAdapter"]
