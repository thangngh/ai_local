from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ai_local.benchmark.models import BenchmarkRunReport


@dataclass(frozen=True)
class BenchmarkHistoryEntry:
    run_id: str
    generated_at: str
    run_mode: str
    ollama_model: str | None
    blended_score: float
    harness_score: float
    llm_score: float | None
    total_tokens: int
    estimated_cost_usd: float
    pass_count: int
    total: int
    active_memory_with_evidence: float = 0.0
    retrieval_mrr: float = 0.0
    parse_rate: float | None = None


def _ollama_parse_rate(report: BenchmarkRunReport) -> float | None:
    if report.run_mode != "harness+ollama":
        return None
    parsed = 0
    total = 0
    for task in report.tasks:
        ollama = task.debug_trace.get("ollama")
        if not isinstance(ollama, dict):
            continue
        total += 1
        if ollama.get("parsed_decision") or (ollama.get("parsed") or {}).get("parsed_decision"):
            parsed += 1
    if total == 0:
        return None
    return round(parsed / total, 4)


def append_benchmark_history(report: BenchmarkRunReport, history_path: Path) -> BenchmarkHistoryEntry:
    entry = BenchmarkHistoryEntry(
        run_id=report.run_id,
        generated_at=report.generated_at,
        run_mode=report.run_mode,
        ollama_model=report.ollama_model,
        blended_score=report.aggregate.system_score,
        harness_score=report.aggregate.harness_system_score,
        llm_score=report.aggregate.llm_system_score,
        total_tokens=report.cost.total_tokens,
        estimated_cost_usd=report.cost.estimated_cost_usd,
        pass_count=report.aggregate.pass_count,
        total=report.aggregate.total,
        active_memory_with_evidence=report.aggregate.memory_metrics.active_memory_with_evidence,
        retrieval_mrr=report.aggregate.retrieval_metrics.mrr,
        parse_rate=_ollama_parse_rate(report),
    )
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry.__dict__, sort_keys=True) + "\n")
    return entry


def load_benchmark_history(history_path: Path, *, limit: int = 10) -> list[BenchmarkHistoryEntry]:
    if not history_path.exists():
        return []
    entries: list[BenchmarkHistoryEntry] = []
    for line in history_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        entries.append(BenchmarkHistoryEntry(**payload))
    return entries[-limit:]


def render_trend_table(entries: list[BenchmarkHistoryEntry]) -> str:
    if not entries:
        return "No benchmark history entries found."
    lines = [
        "BENCHMARK_TREND",
        "run_id                         mode              blend  harness  llm    mem_ev  mrr   parse pass",
    ]
    for entry in entries:
        llm = f"{entry.llm_score:.2f}" if entry.llm_score is not None else "  -  "
        parse = f"{entry.parse_rate:.2f}" if entry.parse_rate is not None else "  - "
        lines.append(
            f"{entry.run_id:30} {entry.run_mode:16} "
            f"{entry.blended_score:5.2f} {entry.harness_score:7.2f} {llm:5} "
            f"{entry.active_memory_with_evidence:5.2f} {entry.retrieval_mrr:4.2f} {parse:5} "
            f"{entry.pass_count}/{entry.total}"
        )
    if len(entries) >= 2:
        first, last = entries[0], entries[-1]
        mrr_delta = last.retrieval_mrr - first.retrieval_mrr
        mem_delta = last.active_memory_with_evidence - first.active_memory_with_evidence
        lines.append("")
        lines.append(
            f"DELTA ({first.run_id} -> {last.run_id}) "
            f"mrr={mrr_delta:+.4f} active_memory_with_evidence={mem_delta:+.4f}"
        )
    return "\n".join(lines)
