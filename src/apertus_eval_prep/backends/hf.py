from __future__ import annotations

import time
from threading import Thread

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer

from apertus_eval_prep.backends import Generation


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


class HFBackend:
    name = "hf"

    def __init__(self, model_id: str, tokenizer_id: str, revision: str | None, dtype_name: str, seed: int):
        self.device = detect_device()
        torch.manual_seed(seed)
        if self.device == "cuda":
            torch.cuda.manual_seed_all(seed)
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_id, revision=revision)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        dtype = resolve_dtype(dtype_name, self.device)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            revision=revision,
            torch_dtype=dtype,
        )
        self.model.to(self.device)
        self.model.eval()

    def generate_one(self, prompt: str, max_new_tokens: int) -> Generation:
        encoded = self.tokenizer(prompt, return_tensors="pt")
        encoded = {k: v.to(self.device) for k, v in encoded.items()}
        streamer = TextIteratorStreamer(
            self.tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )
        kwargs = dict(
            **encoded,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=self.tokenizer.pad_token_id,
            streamer=streamer,
        )
        thread = Thread(target=self.model.generate, kwargs=kwargs)
        t0 = time.perf_counter()
        thread.start()
        ttft = None
        chunks: list[str] = []
        for piece in streamer:
            if ttft is None:
                ttft = (time.perf_counter() - t0) * 1000.0
            chunks.append(piece)
        thread.join()
        e2e = (time.perf_counter() - t0) * 1000.0
        text = "".join(chunks)
        token_count = len(self.tokenizer.encode(text, add_special_tokens=False)) if text else 0
        return Generation(text=text, ttft_ms=ttft, e2e_ms=e2e, num_new_tokens=token_count)
