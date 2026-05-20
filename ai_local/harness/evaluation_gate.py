from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    correctness: float
    completeness: float
    evidence_quality: float
    requirement_match: float
    test_status: float
    ambiguity: float
    risk: float
    expected_band: str
    hop_depth: int
    noise_type: str | None


@dataclass(frozen=True)
class EvaluationLevel:
    name: str
    max_hop_depth: int
    cases: list[EvaluationCase]
    required_to_promote: bool
    description: str


@dataclass(frozen=True)
class EvaluationGateResult:
    level: str
    passed: bool
    checked_case_ids: list[str]
    max_hop_depth: int
    reason: str = ""


def evaluation_score(case: EvaluationCase) -> float:
    return (
        0.25 * case.correctness
        + 0.20 * case.completeness
        + 0.20 * case.evidence_quality
        + 0.15 * case.requirement_match
        + 0.10 * case.test_status
        - 0.10 * case.ambiguity
        - 0.10 * case.risk
    )


def infer_evaluation_band(case: EvaluationCase) -> str:
    score = evaluation_score(case)
    if case.risk >= 0.85:
        return "stop"
    if case.ambiguity >= 0.60:
        return "ask_user"
    if case.evidence_quality <= 0.40:
        return "verify"
    if case.requirement_match <= 0.40:
        return "retry"
    if score >= 0.80 and case.risk < 0.50 and case.test_status >= 0.50:
        return "accept"
    if score >= 0.60:
        return "retry"
    return "ask_user"


def load_evaluation_levels(config_path: Path) -> list[EvaluationLevel]:
    data = load_yaml(config_path)
    levels = data.get("evaluation_gate_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid evaluation gate config in {config_path}"
        raise ValueError(msg)

    loaded: list[EvaluationLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        max_hop_depth = int(definition["max_hop_depth"])
        cases = [
            EvaluationCase(
                id=str(case["id"]),
                correctness=float(case["correctness"]),
                completeness=float(case["completeness"]),
                evidence_quality=float(case["evidence_quality"]),
                requirement_match=float(case["requirement_match"]),
                test_status=float(case["test_status"]),
                ambiguity=float(case["ambiguity"]),
                risk=float(case["risk"]),
                expected_band=str(case["expected_band"]),
                hop_depth=int(case.get("hop_depth", max_hop_depth)),
                noise_type=str(case["noise_type"]) if "noise_type" in case else None,
            )
            for case in definition.get("cases", [])
            if isinstance(case, dict)
        ]
        loaded.append(
            EvaluationLevel(
                name=level_name,
                max_hop_depth=max_hop_depth,
                cases=cases,
                required_to_promote=bool(definition.get("required_to_promote", True)),
                description=str(definition.get("description", "")),
            )
        )
    return loaded


def validate_evaluation_level(level: EvaluationLevel) -> EvaluationGateResult:
    checked_case_ids: list[str] = []
    for case in level.cases:
        checked_case_ids.append(case.id)
        if case.hop_depth > level.max_hop_depth:
            return EvaluationGateResult(
                level.name,
                False,
                checked_case_ids,
                level.max_hop_depth,
                f"{case.id} exceeds max hop depth",
            )
        actual = infer_evaluation_band(case)
        if actual != case.expected_band:
            return EvaluationGateResult(
                level.name,
                False,
                checked_case_ids,
                level.max_hop_depth,
                f"{case.id} expected {case.expected_band}, got {actual}",
            )
    return EvaluationGateResult(level.name, True, checked_case_ids, level.max_hop_depth)


def run_evaluation_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[EvaluationGateResult]:
    results: list[EvaluationGateResult] = []
    for level in load_evaluation_levels(config_path):
        result = validate_evaluation_level(level)
        results.append(result)
        if level.name == max_level:
            break
        if level.required_to_promote and not result.passed:
            break
    return results

