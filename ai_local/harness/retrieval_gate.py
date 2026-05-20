from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class RetrievalCase:
    id: str
    query: str
    noise_type: str
    expected_action: str
    expected_decision: str
    hop_depth: int


@dataclass(frozen=True)
class RetrievalLevel:
    name: str
    max_hop_depth: int
    cases: list[RetrievalCase]
    required_to_promote: bool
    description: str


@dataclass(frozen=True)
class RetrievalGateResult:
    level: str
    passed: bool
    checked_case_ids: list[str]
    max_hop_depth: int
    reason: str = ""


def infer_retrieval_decision(case: RetrievalCase) -> str:
    if case.noise_type == "bilingual_prompt_laundering":
        return "stop"
    if case.noise_type == "deep_chain_interference":
        return "ask_user"
    if case.noise_type == "prompt_injection":
        return "quarantine"
    if case.noise_type in {"stale_memory", "wrong_flow_match"}:
        return "verify"
    if case.noise_type == "source_conflict":
        return "ask_user"
    return "continue"


def load_retrieval_levels(config_path: Path) -> list[RetrievalLevel]:
    data = load_yaml(config_path)
    levels = data.get("retrieval_gate_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid retrieval gate config in {config_path}"
        raise ValueError(msg)

    loaded: list[RetrievalLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        max_hop_depth = int(definition["max_hop_depth"])
        cases = [
            RetrievalCase(
                id=str(case["id"]),
                query=str(case["query"]),
                noise_type=str(case["noise_type"]),
                expected_action=str(case["expected_action"]),
                expected_decision=str(case["expected_decision"]),
                hop_depth=int(case.get("hop_depth", max_hop_depth)),
            )
            for case in definition.get("cases", [])
            if isinstance(case, dict)
        ]
        loaded.append(
            RetrievalLevel(
                name=level_name,
                max_hop_depth=max_hop_depth,
                cases=cases,
                required_to_promote=bool(definition.get("required_to_promote", True)),
                description=str(definition.get("description", "")),
            )
        )
    return loaded


def validate_retrieval_level(level: RetrievalLevel) -> RetrievalGateResult:
    checked_case_ids: list[str] = []
    for case in level.cases:
        checked_case_ids.append(case.id)
        if case.hop_depth > level.max_hop_depth:
            return RetrievalGateResult(
                level=level.name,
                passed=False,
                checked_case_ids=checked_case_ids,
                max_hop_depth=level.max_hop_depth,
                reason=f"{case.id} exceeds max hop depth",
            )
        actual_decision = infer_retrieval_decision(case)
        if actual_decision != case.expected_decision:
            return RetrievalGateResult(
                level=level.name,
                passed=False,
                checked_case_ids=checked_case_ids,
                max_hop_depth=level.max_hop_depth,
                reason=f"{case.id} expected {case.expected_decision}, got {actual_decision}",
            )
        if not case.expected_action:
            return RetrievalGateResult(
                level=level.name,
                passed=False,
                checked_case_ids=checked_case_ids,
                max_hop_depth=level.max_hop_depth,
                reason=f"{case.id} has no expected action",
            )
    return RetrievalGateResult(
        level=level.name,
        passed=True,
        checked_case_ids=checked_case_ids,
        max_hop_depth=level.max_hop_depth,
    )


def run_retrieval_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[RetrievalGateResult]:
    results: list[RetrievalGateResult] = []
    for level in load_retrieval_levels(config_path):
        result = validate_retrieval_level(level)
        results.append(result)
        if level.name == max_level:
            break
        if level.required_to_promote and not result.passed:
            break
    return results

