from __future__ import annotations

import logging
import time
import warnings
from threading import Thread

import torch
from transformers import AutoTokenizer, TextIteratorStreamer

from apertus_eval_prep.backends import Generation
from apertus_eval_prep.backends.hf_load import load_causal_lm, patch_stale_cache_api
from apertus_eval_prep.config import RunConfig

_patch_stale_cache_api = patch_stale_cache_api
_load_causal_lm = load_causal_lm


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


def load_dtype(cfg: RunConfig, device: str) -> torch.dtype:
    """Dtype used when loading the model. Quantized CUDA loads use fp16 (T4 has no native bf16)."""
    dtype = resolve_dtype(cfg.dtype, device)
    if cfg.quantization != "none" and device == "cuda":
        return torch.float16
    return dtype


def suppress_quantization_warnings() -> None:
    """bitsandbytes logs MatMul8bitLt cast warnings on every forward pass — hide that noise."""
    logging.getLogger("bitsandbytes").setLevel(logging.ERROR)
    logging.getLogger("bitsandbytes.autograd._functions").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", message=".*MatMul8bitLt.*")
    warnings.filterwarnings("ignore", module=r"bitsandbytes\..*")


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
        return BitsAndBytesConfig(
            load_in_8bit=True,
            bnb_8bit_compute_dtype=compute_dtype,
        )
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
        if cfg.quantization != "none":
            suppress_quantization_warnings()
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
        dtype = load_dtype(cfg, self.device)
        quant = _quant_config(cfg.quantization, dtype)
        _patch_stale_cache_api()
        load_kwargs: dict = dict(revision=cfg.revision)
        if quant is not None:
            load_kwargs["quantization_config"] = quant
            load_kwargs["device_map"] = "auto"
            load_kwargs["torch_dtype"] = dtype
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
