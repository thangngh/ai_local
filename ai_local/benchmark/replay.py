from __future__ import annotations

import json
from pathlib import Path

from ai_local.benchmark.models import BenchmarkRunReport, BenchmarkTaskResult


def load_benchmark_report(path: Path) -> BenchmarkRunReport:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return BenchmarkRunReport.model_validate(payload)


def load_tasks_jsonl(path: Path) -> list[BenchmarkTaskResult]:
    tasks: list[BenchmarkTaskResult] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        tasks.append(BenchmarkTaskResult.model_validate(json.loads(line)))
    return tasks


def task_attention_flags(
    task: BenchmarkTaskResult,
    *,
    llm_alert_below: float = 0.70,
) -> list[str]:
    flags: list[str] = []
    if task.failures:
        flags.append(f"failures:{len(task.failures)}")
    if task.result != "pass":
        flags.append(f"result:{task.result}")
    if task.llm_system_score is not None and task.llm_system_score < llm_alert_below:
        flags.append(f"low_llm:{task.llm_system_score:.2f}")
    return flags


def format_task_line(task: BenchmarkTaskResult, *, flags: list[str] | None = None) -> str:
    tokens = ""
    if task.token_usage is not None:
        tokens = (
            f" in={task.token_usage.input_tokens} out={task.token_usage.output_tokens}"
        )
    llm_score = f" llm={task.llm_system_score:.2f}" if task.llm_system_score is not None else ""
    failure_note = f" fail={len(task.failures)}" if task.failures else ""
    flag_note = f" !{','.join(flags)}" if flags else ""
    return (
        f"{task.result.upper():7} {task.task_id:32} {task.category:10} "
        f"h={task.harness_system_score:.2f}{llm_score} blend={task.system_score:.2f}"
        f"{tokens}{failure_note}{flag_note}"
    )


def render_replay_report(
    report: BenchmarkRunReport,
    *,
    llm_alert_below: float = 0.70,
    only_flagged: bool = False,
) -> str:
    lines = [
        f"BENCHMARK_REPLAY run={report.run_id} mode={report.run_mode} "
        f"blend={report.aggregate.system_score:.4f} "
        f"harness={report.aggregate.harness_system_score:.4f}",
    ]
    if report.aggregate.llm_system_score is not None:
        lines[0] += f" llm={report.aggregate.llm_system_score:.4f}"
    if report.cost.total_tokens > 0:
        lines.append(
            f"COST tokens={report.cost.total_tokens} usd={report.cost.estimated_cost_usd:.4f} "
            f"tps={report.cost.output_tokens_per_second:.2f}"
        )

    flagged: list[BenchmarkTaskResult] = []
    for task in report.tasks:
        if task_attention_flags(task, llm_alert_below=llm_alert_below):
            flagged.append(task)

    if flagged:
        lines.append(f"FLAGS {len(flagged)} task(s) need review (llm<{llm_alert_below:.2f} or failures)")
        for task in flagged:
            flags = task_attention_flags(task, llm_alert_below=llm_alert_below)
            lines.append(f"  ! {' '.join(flags)} {task.task_id}")

    lines.append("TASKS")
    for task in report.tasks:
        flags = task_attention_flags(task, llm_alert_below=llm_alert_below)
        if only_flagged and not flags:
            continue
        lines.append(format_task_line(task, flags=flags or None))
        if task.failures:
            lines.append(f"  failures: {', '.join(task.failures[:3])}")

    return "\n".join(lines)
