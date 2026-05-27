from __future__ import annotations

import json
from pathlib import Path

from ai_local.benchmark.models import BenchmarkRunReport, BenchmarkTaskResult


def _task_score_view(task: BenchmarkTaskResult, *, mode: str) -> dict:
    if mode == "harness":
        scores = task.harness_scores
        system = task.harness_system_score
        llm = None
    elif mode == "llm":
        scores = task.llm_scores
        system = task.llm_system_score
        llm = task.llm_system_score
    else:
        scores = task.scores
        system = task.system_score
        llm = task.llm_system_score
    payload = {
        "task_id": task.task_id,
        "category": task.category,
        "result": task.result,
        "system_score": system,
        "failures": task.failures,
        "latency_ms": task.latency_ms,
    }
    if scores is not None:
        payload["scores"] = scores.as_dict()
    if llm is not None:
        payload["llm_system_score"] = llm
    if task.token_usage is not None and mode in {"llm", "blended"}:
        payload["token_usage"] = task.token_usage.model_dump(mode="json")
    return payload


def write_split_score_reports(report: BenchmarkRunReport, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = report.run_id
    written: dict[str, Path] = {}

    for mode in ("harness", "llm", "blended"):
        tasks = [_task_score_view(task, mode=mode) for task in report.tasks]
        if mode == "harness":
            aggregate_score = report.aggregate.harness_system_score
            llm_score = None
        elif mode == "llm":
            aggregate_score = report.aggregate.llm_system_score
            llm_score = report.aggregate.llm_system_score
        else:
            aggregate_score = report.aggregate.system_score
            llm_score = report.aggregate.llm_system_score

        payload = {
            "benchmark_id": report.benchmark_id,
            "run_id": run_id,
            "generated_at": report.generated_at,
            "run_mode": report.run_mode,
            "score_type": mode,
            "ollama_model": report.ollama_model,
            "aggregate_score": aggregate_score,
            "llm_aggregate_score": llm_score,
            "pass_count": report.aggregate.pass_count,
            "total": report.aggregate.total,
            "tasks": tasks,
        }
        if mode == "harness":
            payload["memory_metrics"] = report.aggregate.memory_metrics.model_dump(mode="json")
            payload["retrieval_metrics"] = report.aggregate.retrieval_metrics.model_dump(mode="json")
        path = output_dir / f"{run_id}_{mode}_scores.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written[mode] = path

    latest_aliases = {
        "harness": output_dir / "latest_harness_scores.json",
        "llm": output_dir / "latest_llm_scores.json",
        "blended": output_dir / "latest_blended_scores.json",
    }
    for mode, path in written.items():
        latest_aliases[mode].write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return written
