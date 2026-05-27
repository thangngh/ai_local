from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_chars: int
    output_chars: int
    token_source: str
    eval_duration_ns: int | None = None

    @property
    def tokens_per_second(self) -> float:
        if self.eval_duration_ns is None or self.eval_duration_ns <= 0:
            return 0.0
        seconds = self.eval_duration_ns / 1_000_000_000
        return round(self.output_tokens / seconds, 2) if seconds > 0 else 0.0


def estimate_tokens(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, len(stripped) // 4)


def compute_cost_usd(
    *,
    input_tokens: int,
    output_tokens: int,
    input_usd_per_1m: float,
    output_usd_per_1m: float,
) -> float:
    return round(
        (input_tokens * input_usd_per_1m + output_tokens * output_usd_per_1m) / 1_000_000,
        6,
    )
