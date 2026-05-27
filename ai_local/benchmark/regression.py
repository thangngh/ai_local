from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path

from ai_local.benchmark.history import BenchmarkHistoryEntry
from ai_local.benchmark.models import BenchmarkRunReport
from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class RegressionPolicy:
    baseline_strategy: str
    baseline_last_n: int
    max_drop_blended_score: float
    max_drop_harness_score: float
    max_drop_llm_score: float
    max_drop_active_memory_with_evidence: float
    max_drop_retrieval_mrr: float
    max_drop_parse_rate: float
    max_drop_pass_count: int
    min_baseline_entries: int


def load_regression_policy(config_path: Path) -> RegressionPolicy:
    data = load_yaml(config_path)
    section = data.get("regression", data)
    if not isinstance(section, dict):
        section = {}
    return RegressionPolicy(
        baseline_strategy=str(section.get("baseline_strategy", "median")),
        baseline_last_n=int(section.get("baseline_last_n", 5)),
        max_drop_blended_score=float(section.get("max_drop_blended_score", 0.04)),
        max_drop_harness_score=float(section.get("max_drop_harness_score", 0.04)),
        max_drop_llm_score=float(section.get("max_drop_llm_score", 0.05)),
        max_drop_active_memory_with_evidence=float(
            section.get("max_drop_active_memory_with_evidence", 0.05)
        ),
        max_drop_retrieval_mrr=float(section.get("max_drop_retrieval_mrr", 0.08)),
        max_drop_parse_rate=float(section.get("max_drop_parse_rate", 0.10)),
        max_drop_pass_count=int(section.get("max_drop_pass_count", 1)),
        min_baseline_entries=int(section.get("min_baseline_entries", 2)),
    )


def _load_history_entries(history_path: Path) -> list[BenchmarkHistoryEntry]:
    if not history_path.exists():
        return []
    entries: list[BenchmarkHistoryEntry] = []
    for line in history_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        payload.setdefault("pack", "golden")
        entries.append(BenchmarkHistoryEntry(**payload))
    return entries


def _aggregate_value(values: list[float], strategy: str) -> float:
    if not values:
        return 0.0
    if strategy == "max":
        return max(values)
    if strategy == "mean":
        return statistics.mean(values)
    return statistics.median(values)


def _baseline_entries(
    entries: list[BenchmarkHistoryEntry],
    *,
    run_mode: str,
    task_pack: str,
    exclude_run_id: str,
    policy: RegressionPolicy,
) -> list[BenchmarkHistoryEntry]:
    filtered = [
        entry
        for entry in entries
        if entry.run_mode == run_mode
        and entry.pack == task_pack
        and entry.run_id != exclude_run_id
    ]
    if policy.baseline_last_n > 0:
        filtered = filtered[-policy.baseline_last_n :]
    return filtered


def compute_regression_baseline(
    history_path: Path,
    *,
    run_mode: str,
    task_pack: str,
    exclude_run_id: str,
    policy: RegressionPolicy,
) -> dict[str, float | int | None] | None:
    entries = _baseline_entries(
        _load_history_entries(history_path),
        run_mode=run_mode,
        task_pack=task_pack,
        exclude_run_id=exclude_run_id,
        policy=policy,
    )
    if len(entries) < policy.min_baseline_entries:
        return None
    strategy = policy.baseline_strategy
    llm_scores = [entry.llm_score for entry in entries if entry.llm_score is not None]
    parse_rates = [entry.parse_rate for entry in entries if entry.parse_rate is not None]
    return {
        "blended_score": _aggregate_value([e.blended_score for e in entries], strategy),
        "harness_score": _aggregate_value([e.harness_score for e in entries], strategy),
        "llm_score": _aggregate_value(llm_scores, strategy) if llm_scores else None,
        "active_memory_with_evidence": _aggregate_value(
            [e.active_memory_with_evidence for e in entries],
            strategy,
        ),
        "retrieval_mrr": _aggregate_value([e.retrieval_mrr for e in entries], strategy),
        "parse_rate": _aggregate_value(parse_rates, strategy) if parse_rates else None,
        "pass_count": int(_aggregate_value([float(e.pass_count) for e in entries], strategy)),
        "baseline_runs": len(entries),
    }


def _report_from_json(report_path: Path) -> BenchmarkRunReport:
    from ai_local.benchmark.replay import load_benchmark_report

    return load_benchmark_report(report_path)


def _current_metrics(report: BenchmarkRunReport) -> dict[str, float | int | None]:
    from ai_local.benchmark.history import _ollama_parse_rate

    return {
        "blended_score": report.aggregate.system_score,
        "harness_score": report.aggregate.harness_system_score,
        "llm_score": report.aggregate.llm_system_score,
        "active_memory_with_evidence": report.aggregate.memory_metrics.active_memory_with_evidence,
        "retrieval_mrr": report.aggregate.retrieval_metrics.mrr,
        "parse_rate": _ollama_parse_rate(report),
        "pass_count": report.aggregate.pass_count,
    }


def enforce_regression_gate(
    report: BenchmarkRunReport,
    *,
    history_path: Path,
    policy: RegressionPolicy,
    task_pack: str = "golden",
) -> list[str]:
    baseline = compute_regression_baseline(
        history_path,
        run_mode=report.run_mode,
        task_pack=task_pack,
        exclude_run_id=report.run_id,
        policy=policy,
    )
    if baseline is None:
        return []
    current = _current_metrics(report)
    violations: list[str] = []

    def check_drop(
        metric: str,
        current_value: float | int | None,
        baseline_value: float | int | None,
        max_drop: float | int,
    ) -> None:
        if current_value is None or baseline_value is None:
            return
        if isinstance(max_drop, int):
            if int(current_value) < int(baseline_value) - max_drop:
                violations.append(
                    f"{metric} dropped to {current_value} vs baseline {baseline_value}"
                )
            return
        drop = float(baseline_value) - float(current_value)
        if drop > float(max_drop):
            violations.append(
                f"{metric} dropped {drop:.4f} vs baseline {float(baseline_value):.4f}"
            )

    check_drop(
        "blended_score",
        current["blended_score"],
        baseline["blended_score"],
        policy.max_drop_blended_score,
    )
    check_drop(
        "harness_score",
        current["harness_score"],
        baseline["harness_score"],
        policy.max_drop_harness_score,
    )
    check_drop("llm_score", current["llm_score"], baseline["llm_score"], policy.max_drop_llm_score)
    check_drop(
        "active_memory_with_evidence",
        current["active_memory_with_evidence"],
        baseline["active_memory_with_evidence"],
        policy.max_drop_active_memory_with_evidence,
    )
    check_drop(
        "retrieval_mrr",
        current["retrieval_mrr"],
        baseline["retrieval_mrr"],
        policy.max_drop_retrieval_mrr,
    )
    check_drop(
        "parse_rate",
        current["parse_rate"],
        baseline["parse_rate"],
        policy.max_drop_parse_rate,
    )
    check_drop(
        "pass_count",
        current["pass_count"],
        baseline["pass_count"],
        policy.max_drop_pass_count,
    )
    return violations


def enforce_regression_gate_from_paths(
    *,
    report_path: Path,
    history_path: Path,
    policy: RegressionPolicy,
    task_pack: str | None = None,
) -> list[str]:
    report = _report_from_json(report_path)
    resolved_pack = task_pack or (
        "golden+adversarial" if report.benchmark_id.endswith("_adv") else "golden"
    )
    return enforce_regression_gate(
        report,
        history_path=history_path,
        policy=policy,
        task_pack=resolved_pack,
    )
