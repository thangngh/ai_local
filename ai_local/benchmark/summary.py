from __future__ import annotations

from pathlib import Path

from ai_local.benchmark.models import BenchmarkRunReport, BenchmarkTaskResult


def _score_cell(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


def _token_cell(task: BenchmarkTaskResult) -> str:
    if task.token_usage is None:
        return "-"
    return f"{task.token_usage.input_tokens}/{task.token_usage.output_tokens}"


def render_summary_table(report: BenchmarkRunReport) -> str:
    header = (
        "| task_id | category | result | harness | llm | blended | tokens in/out | "
        "latency_ms | top failure |"
    )
    separator = "|---|---|---:|---:|---:|---:|---|---:|---|"
    rows = [header, separator]
    for task in report.tasks:
        top_failure = task.failures[0] if task.failures else "-"
        if len(top_failure) > 48:
            top_failure = top_failure[:45] + "..."
        rows.append(
            "| "
            + " | ".join(
                [
                    task.task_id,
                    task.category,
                    task.result,
                    _score_cell(task.harness_system_score),
                    _score_cell(task.llm_system_score),
                    _score_cell(task.system_score),
                    _token_cell(task),
                    str(task.latency_ms or "-"),
                    top_failure,
                ]
            )
            + " |"
        )
    aggregate = report.aggregate
    rows.append("")
    rows.append(
        f"**Run** `{report.run_id}` | mode={report.run_mode} | "
        f"passed={aggregate.pass_count}/{aggregate.total} | "
        f"blend={aggregate.system_score:.4f} | harness={aggregate.harness_system_score:.4f}"
        + (
            f" | llm={aggregate.llm_system_score:.4f}"
            if aggregate.llm_system_score is not None
            else ""
        )
    )
    if report.cost.total_tokens > 0:
        rows.append(
            f"**Cost** tokens={report.cost.total_tokens} "
            f"(in={report.cost.total_input_tokens} out={report.cost.total_output_tokens}) "
            f"usd={report.cost.estimated_cost_usd} tps={report.cost.output_tokens_per_second}"
        )
    return "\n".join(rows)


def write_summary_markdown(report: BenchmarkRunReport, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    content = "# Benchmark Summary\n\n" + render_summary_table(report) + "\n"
    output.write_text(content, encoding="utf-8")
    return output
