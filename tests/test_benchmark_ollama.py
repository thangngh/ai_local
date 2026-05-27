from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ai_local.benchmark.models import GoldenTask
from ai_local.benchmark.ollama_eval import (
    build_benchmark_prompt,
    evaluate_ollama_response,
    parse_ollama_response,
)
from ai_local.benchmark.runner import load_ollama_benchmark_config, run_golden_benchmark
from ai_local.llm.ollama import OllamaChatResult, OllamaClient, OllamaConfig
from ai_local.llm.tokens import TokenUsage


def _chat_result(content: str, *, input_tokens: int = 10, output_tokens: int = 5) -> OllamaChatResult:
    usage = TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        input_chars=40,
        output_chars=len(content),
        token_source="ollama_api",
        eval_duration_ns=100_000_000,
    )
    return OllamaChatResult(
        content=content,
        latency_ms=10,
        model="qwen2.5:0.5b",
        token_usage=usage,
    )


def test_parse_ollama_response_template() -> None:
    parsed = parse_ollama_response(
        "DECISION: quarantine\nEVIDENCE: README.md\nRATIONALE: injection detected\n"
    )
    assert parsed["decision"] == "quarantine"
    assert parsed["evidence_refs"] == ["README.md"]


def test_build_benchmark_prompt_includes_task_fields() -> None:
    payload = json.loads(Path("golden_tasks/detect_prompt_injection/task.json").read_text(encoding="utf-8"))
    task = GoldenTask.model_validate(payload)
    prompt = build_benchmark_prompt(task)
    assert task.task_id in prompt
    assert task.expected_behavior in prompt


def test_evaluate_ollama_response_scores_refusal() -> None:
    payload = json.loads(Path("golden_tasks/detect_prompt_injection/task.json").read_text(encoding="utf-8"))
    task = GoldenTask.model_validate(payload)
    outcome = evaluate_ollama_response(
        task,
        _chat_result("DECISION: refuse\nEVIDENCE: none\nRATIONALE: prompt injection blocked\n"),
    )
    assert outcome.scores.task_success == 1.0
    assert outcome.scores.safety_score == 1.0


def test_load_ollama_benchmark_config() -> None:
    config = load_ollama_benchmark_config(Path("configs/benchmark_ollama.yaml"))
    assert config.model == "qwen2.5:0.5b"
    assert config.harness_weight == 0.5


@patch.object(OllamaClient, "chat")
@patch.object(OllamaClient, "ensure_model")
@patch.object(OllamaClient, "health_check", return_value=True)
def test_run_golden_benchmark_with_ollama_mock(
    _health: object,
    _ensure: object,
    chat: object,
) -> None:
    chat.return_value = _chat_result(
        "DECISION: continue\nEVIDENCE: ai_local/queue/worker.py\nRATIONALE: ok\n",
        input_tokens=120,
        output_tokens=30,
    )
    from ai_local.benchmark.ollama_eval import OllamaBenchmarkConfig

    report = run_golden_benchmark(
        tasks_root=Path("golden_tasks"),
        benchmark_id="test_ollama_bench",
        ollama_config=OllamaBenchmarkConfig(),
    )
    assert report.run_mode == "harness+ollama"
    assert report.ollama_model == "qwen2.5:0.5b"
    assert report.aggregate.total == 20
    assert all("ollama" in task.debug_trace for task in report.tasks)
    assert report.cost.total_input_tokens > 0
    assert report.cost.total_output_tokens > 0
    assert all(task.token_usage is not None for task in report.tasks)


@pytest.mark.integration
def test_ollama_live_health_check() -> None:
    client = OllamaClient(OllamaConfig())
    if not client.health_check():
        pytest.skip("Ollama is not running locally")
    client.ensure_model("qwen2.5:0.5b")
