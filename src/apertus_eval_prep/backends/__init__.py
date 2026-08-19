from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Generation:
    text: str
    ttft_ms: float | None
    e2e_ms: float
    num_new_tokens: int

    @property
    def tokens_per_sec(self) -> float | None:
        if self.e2e_ms <= 0 or self.num_new_tokens <= 0:
            return None
        return self.num_new_tokens / (self.e2e_ms / 1000.0)
