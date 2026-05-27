from __future__ import annotations

from ai_local.benchmark.models import BenchmarkCostAggregate, BenchmarkTaskResult, TaskTokenUsage
from ai_local.benchmark.ollama_eval import OllamaBenchmarkConfig
from ai_local.llm.tokens import compute_cost_usd


def token_usage_from_debug(debug: dict[str, object]) -> TaskTokenUsage | None:
    ollama = debug.get("ollama")
    if not isinstance(ollama, dict):
        return None
    tokens = ollama.get("tokens")
    if not isinstance(tokens, dict):
        return None
    return TaskTokenUsage(
        input_tokens=int(tokens.get("input_tokens", 0)),
        output_tokens=int(tokens.get("output_tokens", 0)),
        total_tokens=int(tokens.get("total_tokens", 0)),
        input_chars=int(tokens.get("input_chars", 0)),
        output_chars=int(tokens.get("output_chars", 0)),
        latency_ms=int(ollama.get("ollama_latency_ms", 0)),
        tokens_per_second=float(tokens.get("tokens_per_second", 0.0)),
        estimated_cost_usd=float(tokens.get("estimated_cost_usd", 0.0)),
        token_source=str(tokens.get("token_source", "unknown")),
        eval_duration_ns=int(tokens["eval_duration_ns"])
        if tokens.get("eval_duration_ns") is not None
        else None,
    )


def attach_task_token_usage(
    result: BenchmarkTaskResult,
    *,
    ollama_config: OllamaBenchmarkConfig | None,
) -> BenchmarkTaskResult:
    usage = token_usage_from_debug(result.debug_trace)
    if usage is None:
        return result
    if ollama_config is not None and usage.estimated_cost_usd == 0.0:
        cost = compute_cost_usd(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            input_usd_per_1m=ollama_config.input_usd_per_1m,
            output_usd_per_1m=ollama_config.output_usd_per_1m,
        )
        usage = usage.model_copy(update={"estimated_cost_usd": cost})
    return result.model_copy(update={"token_usage": usage})


def build_cost_aggregate(
    results: list[BenchmarkTaskResult],
    *,
    ollama_config: OllamaBenchmarkConfig | None,
) -> BenchmarkCostAggregate:
    usages = [result.token_usage for result in results if result.token_usage is not None]
    if not usages:
        return BenchmarkCostAggregate()

    total_input = sum(item.input_tokens for item in usages)
    total_output = sum(item.output_tokens for item in usages)
    total_latency = sum(item.latency_ms for item in usages)
    total_cost = sum(item.estimated_cost_usd for item in usages)
    eval_ns = [item.eval_duration_ns for item in usages if item.eval_duration_ns]
    output_tps = 0.0
    if eval_ns:
        seconds = sum(eval_ns) / 1_000_000_000
        if seconds > 0:
            output_tps = round(total_output / seconds, 2)

    if ollama_config is not None and total_cost == 0.0:
        total_cost = compute_cost_usd(
            input_tokens=total_input,
            output_tokens=total_output,
            input_usd_per_1m=ollama_config.input_usd_per_1m,
            output_usd_per_1m=ollama_config.output_usd_per_1m,
        )

    task_count = len(usages)
    return BenchmarkCostAggregate(
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_tokens=total_input + total_output,
        total_latency_ms=total_latency,
        estimated_cost_usd=round(total_cost, 6),
        output_tokens_per_second=output_tps,
        avg_input_tokens_per_task=round(total_input / task_count, 2),
        avg_output_tokens_per_task=round(total_output / task_count, 2),
        avg_cost_usd_per_task=round(total_cost / task_count, 6),
    )
