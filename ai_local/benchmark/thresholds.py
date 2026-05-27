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
    adversarial_min_system_score: float | None = None
    adversarial_max_fail_count: int | None = None
    adversarial_min_safety_score: float | None = None


def load_benchmark_thresholds(config_path: Path) -> BenchmarkThresholds:
    data = load_yaml(config_path)
    harness = data.get("harness", {})
    ollama = data.get("ollama", {})
    adversarial = data.get("adversarial", {})
    if not isinstance(harness, dict):
        harness = {}
    if not isinstance(ollama, dict):
        ollama = {}
    if not isinstance(adversarial, dict):
        adversarial = {}
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
        adversarial_min_system_score=float(adversarial["min_system_score"])
        if "min_system_score" in adversarial
        else None,
        adversarial_max_fail_count=int(adversarial["max_fail_count"])
        if "max_fail_count" in adversarial
        else None,
        adversarial_min_safety_score=float(adversarial["min_safety_score"])
        if "min_safety_score" in adversarial
        else None,
    )


def _mean_safety_score(report: BenchmarkRunReport) -> float:
    safety_tasks = [task for task in report.tasks if task.category == "safety"]
    if not safety_tasks:
        return report.aggregate.system_score
    return sum(task.harness_scores.safety_score for task in safety_tasks) / len(safety_tasks)


def enforce_thresholds(
    report: BenchmarkRunReport,
    thresholds: BenchmarkThresholds,
    *,
    adversarial_pack: bool = False,
) -> list[str]:
    violations: list[str] = []
    min_score = thresholds.harness_min_system_score
    max_fails = thresholds.harness_max_fail_count
    if adversarial_pack:
        if thresholds.adversarial_min_system_score is not None:
            min_score = thresholds.adversarial_min_system_score
        if thresholds.adversarial_max_fail_count is not None:
            max_fails = thresholds.adversarial_max_fail_count
    if report.aggregate.harness_system_score < min_score:
        violations.append(
            f"harness score {report.aggregate.harness_system_score} < {min_score}"
        )
    if report.aggregate.fail_count > max_fails:
        violations.append(f"fail_count {report.aggregate.fail_count} > {max_fails}")
    if adversarial_pack and thresholds.adversarial_min_safety_score is not None:
        safety = _mean_safety_score(report)
        if safety < thresholds.adversarial_min_safety_score:
            violations.append(
                f"safety score {safety:.4f} < {thresholds.adversarial_min_safety_score}"
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
