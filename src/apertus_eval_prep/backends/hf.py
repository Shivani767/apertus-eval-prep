from __future__ import annotations

import time
from threading import Thread

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer

from apertus_eval_prep.backends import Generation
from apertus_eval_prep.config import RunConfig


def _patch_stale_cache_api() -> None:
    """Hub modeling_phi3.py still reads Cache APIs removed in recent transformers."""
    try:
        from transformers.cache_utils import Cache
    except ImportError:
        return
    if not hasattr(Cache, "seen_tokens"):
        Cache.seen_tokens = property(
            lambda self: int(self.get_seq_length()) if hasattr(self, "get_seq_length") else 0
        )
    if not hasattr(Cache, "get_max_length"):

        def _get_max_length(self):
            fn = getattr(self, "get_max_cache_shape", None)
            return fn() if callable(fn) else None

        Cache.get_max_length = _get_max_length


def _load_causal_lm(model_id: str, load_kwargs: dict):
    """Prefer native transformers classes. Phi-3.5 remote code crashes on DynamicCache."""
    native = dict(load_kwargs)
    native["trust_remote_code"] = False
    try:
        return AutoModelForCausalLM.from_pretrained(model_id, **native)
    except ValueError as exc:
        if "trust_remote_code" not in str(exc):
            raise
        remote = dict(load_kwargs)
        remote["trust_remote_code"] = True
        return AutoModelForCausalLM.from_pretrained(model_id, **remote)


def detect_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def resolve_dtype(name: str, device: str) -> torch.dtype:
    mapping = {
        "float32": torch.float32,
        "fp32": torch.float32,
        "float16": torch.float16,
        "fp16": torch.float16,
        "bfloat16": torch.bfloat16,
        "bf16": torch.bfloat16,
    }
    if name != "auto":
        return mapping[name]
    if device == "cuda":
        return torch.bfloat16
    if device == "mps":
        return torch.float16
    return torch.float32


def _quant_config(quantization: str, compute_dtype: torch.dtype):
    if quantization == "none":
        return None
    try:
        from transformers import BitsAndBytesConfig
    except ImportError as exc:
        raise ImportError(
            "int8/int4 need bitsandbytes + CUDA. On Colab: pip install -e '.[gpu]'. "
            "macOS cannot run bitsandbytes quantization."
        ) from exc
    if quantization == "int8":
        return BitsAndBytesConfig(load_in_8bit=True)
    if quantization == "int4":
        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
    raise ValueError(quantization)


class HFBackend:
    name = "hf"

    def __init__(self, cfg: RunConfig):
        self.cfg = cfg
        self.device = detect_device()
        if cfg.quantization != "none" and self.device != "cuda":
            raise RuntimeError(
                f"quantization={cfg.quantization} requires CUDA (Colab T4/A10). "
                f"This machine is {self.device}."
            )
        torch.manual_seed(cfg.seed)
        if self.device == "cuda":
            torch.cuda.manual_seed_all(cfg.seed)
        self.tokenizer = AutoTokenizer.from_pretrained(
            cfg.tokenizer_name(),
            revision=cfg.revision,
            trust_remote_code=True,
        )
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        dtype = resolve_dtype(cfg.dtype, self.device)
        quant = _quant_config(cfg.quantization, dtype)
        _patch_stale_cache_api()
        load_kwargs: dict = dict(revision=cfg.revision)
        if quant is not None:
            load_kwargs["quantization_config"] = quant
            load_kwargs["device_map"] = "auto"
        else:
            load_kwargs["torch_dtype"] = dtype
        self.model = _load_causal_lm(cfg.model_id, load_kwargs)
        if quant is None:
            self.model.to(self.device)
        self.model.eval()

    def generate_one(self, prompt: str, max_new_tokens: int) -> Generation:
        encoded = self.tokenizer(prompt, return_tensors="pt")
        device = next(self.model.parameters()).device
        encoded = {k: v.to(device) for k, v in encoded.items()}
        streamer = TextIteratorStreamer(
            self.tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )
        do_sample = self.cfg.do_sample()
        kwargs = dict(
            **encoded,
            max_new_tokens=max_new_tokens,
            do_sample=do_sample,
            pad_token_id=self.tokenizer.pad_token_id,
            streamer=streamer,
        )
        if do_sample:
            kwargs["temperature"] = self.cfg.temperature
            kwargs["top_p"] = self.cfg.top_p
        errors: list[BaseException] = []

        def _generate() -> None:
            try:
                self.model.generate(**kwargs)
            except BaseException as exc:
                errors.append(exc)
                end = getattr(streamer, "end", None)
                if callable(end):
                    end()

        thread = Thread(target=_generate)
        t0 = time.perf_counter()
        thread.start()
        ttft = None
        chunks: list[str] = []
        for piece in streamer:
            if ttft is None:
                ttft = (time.perf_counter() - t0) * 1000.0
            chunks.append(piece)
        thread.join()
        if errors:
            raise errors[0]
        e2e = (time.perf_counter() - t0) * 1000.0
        text = "".join(chunks)
        token_count = len(self.tokenizer.encode(text, add_special_tokens=False)) if text else 0
        return Generation(text=text, ttft_ms=ttft, e2e_ms=e2e, num_new_tokens=token_count)
