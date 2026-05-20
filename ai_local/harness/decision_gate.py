from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class DecisionCase:
    id: str
    flow: str
    score: float
    risk: float
    ambiguity: float
    retries: int
    expected_decision: str
    hop_depth: int
    security_signal: str | None


@dataclass(frozen=True)
class DecisionLevel:
    name: str
    max_hop_depth: int
    cases: list[DecisionCase]
    required_to_promote: bool
    description: str


@dataclass(frozen=True)
class DecisionGateResult:
    level: str
    passed: bool
    checked_case_ids: list[str]
    max_hop_depth: int
    reason: str = ""


def infer_decision(case: DecisionCase) -> str:
    if case.security_signal == "deep_policy_shadowing" or case.risk > 0.85:
        return "stop"
    if case.security_signal == "tool_policy_override":
        return "quarantine"
    if case.security_signal == "memory_conflict":
        return "verify"
    if case.ambiguity > 0.60:
        return "ask_user"
    if case.security_signal == "laundered_evidence":
        return "ask_user"
    if case.score >= 0.80 and case.risk < 0.50:
        return "accept"
    if 0.60 <= case.score < 0.80 and case.retries < 2:
        return "retry"
    return "ask_user"


def load_decision_levels(config_path: Path) -> list[DecisionLevel]:
    data = load_yaml(config_path)
    levels = data.get("decision_gate_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid decision gate config in {config_path}"
        raise ValueError(msg)

    loaded: list[DecisionLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        cases = [
            DecisionCase(
                id=str(case["id"]),
                flow=str(case["flow"]),
                score=float(case["score"]),
                risk=float(case["risk"]),
                ambiguity=float(case["ambiguity"]),
                retries=int(case["retries"]),
                expected_decision=str(case["expected_decision"]),
                hop_depth=decision_case_hop_depth(case, definition),
                security_signal=(
                    str(case["security_signal"]) if "security_signal" in case else None
                ),
            )
            for case in definition.get("cases", [])
            if isinstance(case, dict)
        ]
        loaded.append(
            DecisionLevel(
                name=level_name,
                max_hop_depth=int(definition["max_hop_depth"]),
                cases=cases,
                required_to_promote=bool(definition.get("required_to_promote", True)),
                description=str(definition.get("description", "")),
            )
        )
    return loaded


def decision_case_hop_depth(case: dict[object, object], definition: dict[object, object]) -> int:
    hop_depth = case.get("hop_depth")
    if isinstance(hop_depth, int):
        return hop_depth
    max_hop_depth = definition.get("max_hop_depth")
    if isinstance(max_hop_depth, int):
        return max_hop_depth
    return 0


def validate_decision_level(level: DecisionLevel) -> DecisionGateResult:
    checked_case_ids: list[str] = []
    for case in level.cases:
        checked_case_ids.append(case.id)
        if case.hop_depth > level.max_hop_depth:
            return DecisionGateResult(
                level=level.name,
                passed=False,
                checked_case_ids=checked_case_ids,
                max_hop_depth=level.max_hop_depth,
                reason=f"{case.id} exceeds max hop depth",
            )
        actual = infer_decision(case)
        if actual != case.expected_decision:
            return DecisionGateResult(
                level=level.name,
                passed=False,
                checked_case_ids=checked_case_ids,
                max_hop_depth=level.max_hop_depth,
                reason=f"{case.id} expected {case.expected_decision}, got {actual}",
            )
    return DecisionGateResult(
        level=level.name,
        passed=True,
        checked_case_ids=checked_case_ids,
        max_hop_depth=level.max_hop_depth,
    )


def run_decision_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[DecisionGateResult]:
    results: list[DecisionGateResult] = []
    for level in load_decision_levels(config_path):
        result = validate_decision_level(level)
        results.append(result)
        if level.name == max_level:
            break
        if level.required_to_promote and not result.passed:
            break
    return results
