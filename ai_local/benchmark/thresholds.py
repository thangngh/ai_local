from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.benchmark.models import BenchmarkRunReport
from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class BenchmarkThresholds:
    harness_min_system_score: float
    harness_max_fail_count: int
    ollama_min_blended_score: float | None
    ollama_min_llm_score: float | None
    ollama_max_total_tokens: int | None


def load_benchmark_thresholds(config_path: Path) -> BenchmarkThresholds:
    data = load_yaml(config_path)
    harness = data.get("harness", {})
    ollama = data.get("ollama", {})
    if not isinstance(harness, dict):
        harness = {}
    if not isinstance(ollama, dict):
        ollama = {}
    return BenchmarkThresholds(
        harness_min_system_score=float(harness.get("min_system_score", 0.95)),
        harness_max_fail_count=int(harness.get("max_fail_count", 0)),
        ollama_min_blended_score=float(ollama["min_blended_score"])
        if "min_blended_score" in ollama
        else None,
        ollama_min_llm_score=float(ollama["min_llm_score"]) if "min_llm_score" in ollama else None,
        ollama_max_total_tokens=int(ollama["max_total_tokens"])
        if "max_total_tokens" in ollama
        else None,
    )


def enforce_thresholds(report: BenchmarkRunReport, thresholds: BenchmarkThresholds) -> list[str]:
    violations: list[str] = []
    if report.aggregate.harness_system_score < thresholds.harness_min_system_score:
        violations.append(
            f"harness score {report.aggregate.harness_system_score} "
            f"< {thresholds.harness_min_system_score}"
        )
    if report.aggregate.fail_count > thresholds.harness_max_fail_count:
        violations.append(
            f"fail_count {report.aggregate.fail_count} > {thresholds.harness_max_fail_count}"
        )
    if report.run_mode == "harness+ollama":
        if (
            thresholds.ollama_min_blended_score is not None
            and report.aggregate.system_score < thresholds.ollama_min_blended_score
        ):
            violations.append(
                f"blended score {report.aggregate.system_score} "
                f"< {thresholds.ollama_min_blended_score}"
            )
        if (
            thresholds.ollama_min_llm_score is not None
            and report.aggregate.llm_system_score is not None
            and report.aggregate.llm_system_score < thresholds.ollama_min_llm_score
        ):
            violations.append(
                f"llm score {report.aggregate.llm_system_score} < {thresholds.ollama_min_llm_score}"
            )
        if (
            thresholds.ollama_max_total_tokens is not None
            and report.cost.total_tokens > thresholds.ollama_max_total_tokens
        ):
            violations.append(
                f"total_tokens {report.cost.total_tokens} > {thresholds.ollama_max_total_tokens}"
            )
    return violations
