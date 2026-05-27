from __future__ import annotations

from ai_local.llm.tokens import TokenUsage, compute_cost_usd, estimate_tokens


def test_estimate_tokens_from_text() -> None:
    assert estimate_tokens("hello world") >= 1


def test_compute_cost_usd() -> None:
    cost = compute_cost_usd(
        input_tokens=1_000_000,
        output_tokens=500_000,
        input_usd_per_1m=1.0,
        output_usd_per_1m=2.0,
    )
    assert cost == 2.0


def test_token_usage_tokens_per_second() -> None:
    usage = TokenUsage(
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        input_chars=40,
        output_chars=80,
        token_source="ollama_api",
        eval_duration_ns=1_000_000_000,
    )
    assert usage.tokens_per_second == 20.0
