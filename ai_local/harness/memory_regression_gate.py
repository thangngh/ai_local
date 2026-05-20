from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class MemoryRegressionCheck:
    id: str
    pattern: str
    expected_active_state: str
    required_doc_match: bool
    required_constraints_restored: int
    expected_decision: str | None


@dataclass(frozen=True)
class MemoryRegressionLevel:
    name: str
    max_state_hops: int
    min_doc_match_score: float
    checks: list[MemoryRegressionCheck]
    required_to_promote: bool
    description: str


@dataclass(frozen=True)
class MemoryRegressionResult:
    level: str
    passed: bool
    checked_ids: list[str]
    max_state_hops: int
    reason: str = ""


def load_memory_regression_levels(config_path: Path) -> list[MemoryRegressionLevel]:
    data = load_yaml(config_path)
    levels = data.get("memory_regression_gate_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid memory regression gate config in {config_path}"
        raise ValueError(msg)

    loaded: list[MemoryRegressionLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        loaded.append(
            MemoryRegressionLevel(
                name=level_name,
                max_state_hops=int(definition["max_state_hops"]),
                min_doc_match_score=float(definition["min_doc_match_score"]),
                checks=[
                    MemoryRegressionCheck(
                        id=str(check["id"]),
                        pattern=str(check["pattern"]),
                        expected_active_state=str(check["expected_active_state"]),
                        required_doc_match=bool(check.get("required_doc_match", False)),
                        required_constraints_restored=int(
                            check.get("required_constraints_restored", 0)
                        ),
                        expected_decision=(
                            str(check["expected_decision"])
                            if "expected_decision" in check
                            else None
                        ),
                    )
                    for check in definition.get("checks", [])
                    if isinstance(check, dict)
                ],
                required_to_promote=bool(definition.get("required_to_promote", True)),
                description=str(definition.get("description", "")),
            )
        )
    return loaded


def count_state_hops(pattern: str) -> int:
    states = [state for state in pattern.split("-") if state]
    if len(states) <= 1:
        return 0
    return sum(1 for previous, current in zip(states, states[1:]) if previous != current)


def validate_memory_regression_level(level: MemoryRegressionLevel) -> MemoryRegressionResult:
    checked_ids: list[str] = []
    if not 0.0 <= level.min_doc_match_score <= 1.0:
        return MemoryRegressionResult(
            level=level.name,
            passed=False,
            checked_ids=checked_ids,
            max_state_hops=level.max_state_hops,
            reason="min_doc_match_score must be between 0 and 1",
        )

    for check in level.checks:
        checked_ids.append(check.id)
        if count_state_hops(check.pattern) > level.max_state_hops:
            return MemoryRegressionResult(
                level=level.name,
                passed=False,
                checked_ids=checked_ids,
                max_state_hops=level.max_state_hops,
                reason=f"{check.id} exceeds max state hops",
            )
        if not check.expected_active_state:
            return MemoryRegressionResult(
                level=level.name,
                passed=False,
                checked_ids=checked_ids,
                max_state_hops=level.max_state_hops,
                reason=f"{check.id} has no expected active state",
            )
    return MemoryRegressionResult(
        level=level.name,
        passed=True,
        checked_ids=checked_ids,
        max_state_hops=level.max_state_hops,
    )


def run_memory_regression_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[MemoryRegressionResult]:
    results: list[MemoryRegressionResult] = []
    for level in load_memory_regression_levels(config_path):
        result = validate_memory_regression_level(level)
        results.append(result)
        if level.name == max_level:
            break
        if level.required_to_promote and not result.passed:
            break
    return results

