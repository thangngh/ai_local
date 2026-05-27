from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from ai_local.benchmark.cost import attach_task_token_usage, build_cost_aggregate
from ai_local.benchmark.evaluators import EvaluationOutcome, evaluate_golden_task
from ai_local.benchmark.metrics import build_aggregate
from ai_local.benchmark.models import BenchmarkRunReport, BenchmarkScores, BenchmarkTaskResult, GoldenTask
from ai_local.benchmark.ollama_eval import OllamaBenchmarkConfig, blend_scores, run_ollama_for_task
from ai_local.benchmark.rubric import compute_system_score
from ai_local.config.loader import load_yaml
from ai_local.llm.ollama import OllamaClient, OllamaConfig, OllamaError


def discover_golden_tasks(tasks_root: Path) -> list[GoldenTask]:
    tasks: list[GoldenTask] = []
    for task_file in sorted(tasks_root.glob("**/task.json")):
        payload = json.loads(task_file.read_text(encoding="utf-8"))
        tasks.append(GoldenTask.model_validate(payload))
    if not tasks:
        msg = f"No golden tasks found under {tasks_root}"
        raise FileNotFoundError(msg)
    return tasks


def _result_label(scores: BenchmarkScores, failures: list[str]) -> str:
    if scores.task_success >= 1.0 and not failures:
        return "pass"
    if scores.task_success >= 0.5 or any(score >= 0.5 for score in scores.as_dict().values()):
        return "partial"
    return "fail"


def load_ollama_benchmark_config(config_path: Path) -> OllamaBenchmarkConfig:
    data = load_yaml(config_path)
    section = data.get("ollama_benchmark", data)
    if not isinstance(section, dict):
        msg = f"Invalid Ollama benchmark config in {config_path}"
        raise ValueError(msg)
    return OllamaBenchmarkConfig(
        base_url=str(section.get("base_url", "http://127.0.0.1:11434")),
        model=str(section.get("model", "qwen2.5:0.5b")),
        timeout_seconds=int(section.get("timeout_seconds", 120)),
        harness_weight=float(section.get("harness_weight", 0.5)),
        input_usd_per_1m=float(section.get("input_usd_per_1m", 0.0)),
        output_usd_per_1m=float(section.get("output_usd_per_1m", 0.0)),
    )


def run_golden_benchmark(
    *,
    tasks_root: Path,
    benchmark_id: str = "local_ai_bench",
    run_id: str | None = None,
    ollama_config: OllamaBenchmarkConfig | None = None,
) -> BenchmarkRunReport:
    tasks = discover_golden_tasks(tasks_root)
    resolved_run_id = run_id or f"run_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
    results: list[BenchmarkTaskResult] = []
    ollama_client: OllamaClient | None = None
    if ollama_config is not None:
        ollama_client = OllamaClient(
            OllamaConfig(
                base_url=ollama_config.base_url,
                model=ollama_config.model,
                timeout_seconds=ollama_config.timeout_seconds,
            )
        )
        if not ollama_client.health_check():
            msg = f"Ollama is not reachable at {ollama_config.base_url}"
            raise OllamaError(msg)
        ollama_client.ensure_model(ollama_config.model)

    for task in tasks:
        harness_outcome = evaluate_golden_task(task)
        outcome = harness_outcome
        if ollama_client is not None and ollama_config is not None:
            llm_outcome = run_ollama_for_task(task, ollama_client, ollama_config=ollama_config)
            blended = blend_scores(
                harness_outcome.scores,
                llm_outcome.scores,
                ollama_config.harness_weight,
            )
            if task.performance_budget_ms is not None:
                llm_latency = int(llm_outcome.debug_trace.get("ollama_latency_ms", 0))
                if llm_latency <= task.performance_budget_ms:
                    blended.performance_score = min(blended.performance_score, 1.0)
                elif llm_latency <= task.performance_budget_ms * 2:
                    blended.performance_score = min(blended.performance_score, 0.5)
                else:
                    blended.performance_score = 0.0
            outcome = EvaluationOutcome(
                passed_criteria=harness_outcome.passed_criteria + llm_outcome.passed_criteria,
                failed_criteria=sorted(set(harness_outcome.failed_criteria + llm_outcome.failed_criteria)),
                scores=blended,
                retrieved_refs=sorted(set(harness_outcome.retrieved_refs + llm_outcome.retrieved_refs)),
                used_memories=sorted(set(harness_outcome.used_memories + llm_outcome.used_memories)),
                tool_calls=harness_outcome.tool_calls + llm_outcome.tool_calls,
                gate_decisions=harness_outcome.gate_decisions + llm_outcome.gate_decisions,
                debug_trace={
                    **harness_outcome.debug_trace,
                    "harness": harness_outcome.debug_trace,
                    "ollama": llm_outcome.debug_trace,
                },
            )

        scores = outcome.scores
        failures = list(outcome.failed_criteria)
        result_label = _result_label(scores, failures)
        latency = outcome.debug_trace.get("latency_ms")
        if ollama_config is not None:
            ollama_latency = outcome.debug_trace.get("ollama", {}).get("ollama_latency_ms")
            if isinstance(ollama_latency, int):
                latency = (latency or 0) + ollama_latency
        task_result = BenchmarkTaskResult(
            benchmark_id=benchmark_id,
            run_id=resolved_run_id,
            task_id=task.task_id,
            category=task.category,
            result=result_label,
            scores=scores,
            system_score=compute_system_score(scores.as_dict()),
            failures=failures,
            retrieved_refs=outcome.retrieved_refs,
            used_memories=outcome.used_memories,
            tool_calls=outcome.tool_calls,
            gate_decisions=outcome.gate_decisions,
            latency_ms=latency,
            debug_trace=outcome.debug_trace,
        )
        results.append(attach_task_token_usage(task_result, ollama_config=ollama_config))

    return BenchmarkRunReport(
        benchmark_id=benchmark_id,
        run_id=resolved_run_id,
        generated_at=datetime.now(UTC).isoformat(),
        run_mode="harness+ollama" if ollama_config is not None else "harness",
        ollama_model=ollama_config.model if ollama_config is not None else None,
        ollama_base_url=ollama_config.base_url if ollama_config is not None else None,
        harness_weight=ollama_config.harness_weight if ollama_config is not None else None,
        cost=build_cost_aggregate(results, ollama_config=ollama_config),
        tasks=results,
        aggregate=build_aggregate(results),
    )


def write_benchmark_report(report: BenchmarkRunReport, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = report.model_dump(mode="json")
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tasks_path = output.parent / f"{report.run_id}_tasks.jsonl"
    with tasks_path.open("w", encoding="utf-8") as handle:
        for task in report.tasks:
            handle.write(json.dumps(task.model_dump(mode="json"), sort_keys=True) + "\n")
    return output
