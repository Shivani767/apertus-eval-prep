from __future__ import annotations

from apertus_eval_prep.backends import Generation


class VLLMBackend:
    name = "vllm"

    def __init__(self, model_id: str, tokenizer_id: str, revision: str | None, dtype_name: str, seed: int):
        try:
            from vllm import LLM, SamplingParams
        except ImportError as exc:
            raise ImportError(
                "vLLM is not installed. Use Colab/Linux+CUDA: pip install 'apertus-eval-prep[gpu]'. "
                "macOS is not supported by vLLM; run configs/vllm.yaml there, not on a Mac."
            ) from exc

        dtype = None if dtype_name == "auto" else dtype_name
        self._SamplingParams = SamplingParams
        self.llm = LLM(
            model=model_id,
            tokenizer=tokenizer_id,
            revision=revision,
            dtype=dtype,
            seed=seed,
            trust_remote_code=True,
        )

    def generate_one(self, prompt: str, max_new_tokens: int) -> Generation:
        # Completion API on an already-rendered string. Do not call llm.chat().
        params = self._SamplingParams(
            temperature=0.0,
            max_tokens=max_new_tokens,
        )
        outputs = self.llm.generate([prompt], params)
        out = outputs[0]
        text = out.outputs[0].text if out.outputs else ""
        num_tokens = len(out.outputs[0].token_ids) if out.outputs else 0
        ttft = None
        e2e = None
        metrics = getattr(out, "metrics", None)
        if metrics is not None:
            arrival = getattr(metrics, "arrival_time", None)
            first = getattr(metrics, "first_token_time", None)
            finished = getattr(metrics, "finished_time", None)
            if arrival is not None and first is not None:
                ttft = (first - arrival) * 1000.0
            if arrival is not None and finished is not None:
                e2e = (finished - arrival) * 1000.0
        if e2e is None:
            e2e = 0.0
        return Generation(text=text, ttft_ms=ttft, e2e_ms=e2e, num_new_tokens=num_tokens)
