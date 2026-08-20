from __future__ import annotations

import sys
from types import ModuleType

from apertus_eval_prep.backends import Generation
from apertus_eval_prep.config import RunConfig


def _stub_torchaudio() -> None:
    for name in list(sys.modules):
        if name == "torchaudio" or name.startswith("torchaudio."):
            del sys.modules[name]
    stub = ModuleType("torchaudio")
    stub.__version__ = "0.0.0+unused-for-text-eval"
    sys.modules["torchaudio"] = stub


def _import_vllm():
    """Import vLLM. Text eval does not need TorchAudio; Colab often breaks that import."""
    try:
        from vllm import LLM, SamplingParams

        return LLM, SamplingParams
    except ImportError as exc:
        if "vllm" in str(exc).lower() and "torchaudio" not in str(exc).lower():
            raise ImportError(
                "vLLM is not installed. Use Colab/Linux+CUDA: pip install 'apertus-eval-prep[gpu]'. "
                "macOS is not supported by vLLM; run configs/vllm.yaml there, not on a Mac."
            ) from exc
        _stub_torchaudio()
    except RuntimeError as exc:
        if "CUDA versions" not in str(exc) and "TorchAudio" not in str(exc):
            raise
        _stub_torchaudio()

    from vllm import LLM, SamplingParams

    return LLM, SamplingParams


class VLLMBackend:
    name = "vllm"

    def __init__(self, cfg: RunConfig):
        if cfg.quantization != "none":
            raise RuntimeError(
                "This harness does not cross vLLM with bitsandbytes quantization "
                "(OFAT would confound backend × quant). Use backend=hf for int8/int4, "
                "or backend=vllm with quantization=none."
            )
        LLM, SamplingParams = _import_vllm()
        dtype = "auto" if cfg.dtype in (None, "auto") else cfg.dtype
        self.cfg = cfg
        self._SamplingParams = SamplingParams
        engine_kwargs = dict(
            model=cfg.model_id,
            tokenizer=cfg.tokenizer_name(),
            dtype=dtype,
            seed=cfg.seed,
            trust_remote_code=True,
        )
        if cfg.revision:
            engine_kwargs["revision"] = cfg.revision
        self.llm = LLM(**engine_kwargs)
        self.device = "cuda"

    def generate_one(self, prompt: str, max_new_tokens: int) -> Generation:
        # Completion API on an already-rendered string. Do not call llm.chat().
        sample_kwargs = dict(
            temperature=self.cfg.temperature if self.cfg.do_sample() else 0.0,
            max_tokens=max_new_tokens,
            seed=self.cfg.seed,
        )
        if self.cfg.do_sample():
            sample_kwargs["top_p"] = self.cfg.top_p
        params = self._SamplingParams(**sample_kwargs)
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
