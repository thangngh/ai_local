from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class KnowledgeCase:
    id: str
    flow: list[str]
    knowledge_level: str
    rank: int
    confidence: float
    evidence_strength: float
    conflict_score: float
    noise_type: str
    expected_decision: str
    hop_depth: int


@dataclass(frozen=True)
class KnowledgeLevel:
    name: str
    max_hop_depth: int
    cases: list[KnowledgeCase]
    required_to_promote: bool
    description: str


@dataclass(frozen=True)
class KnowledgeGateResult:
    level: str
    passed: bool
    checked_case_ids: list[str]
    max_hop_depth: int
    reason: str = ""


def parse_knowledge_flow(flow: str) -> list[str]:
    return [stage.strip() for stage in flow.split("->") if stage.strip()]


def infer_knowledge_decision(case: KnowledgeCase) -> str:
    if case.noise_type == "prompt_injection":
        return "quarantine"
    if case.noise_type == "deep_policy_laundering":
        return "reject"
    if case.conflict_score >= 0.70:
        return "ask_user"
    if case.knowledge_level == "K0_UNKNOWN" or case.rank < 40:
        return "reject"
    if case.evidence_strength <= 0.55:
        return "verify_more"
    if case.rank >= 75 and case.confidence >= 0.70 and case.conflict_score <= 0.50:
        return "use"
    return "verify_more"


def load_knowledge_levels(config_path: Path) -> list[KnowledgeLevel]:
    data = load_yaml(config_path)
    levels = data.get("knowledge_gate_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid knowledge gate config in {config_path}"
        raise ValueError(msg)

    loaded: list[KnowledgeLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        max_hop_depth = int(definition["max_hop_depth"])
        cases = [
            KnowledgeCase(
                id=str(case["id"]),
                flow=parse_knowledge_flow(str(case["flow"])),
                knowledge_level=str(case["knowledge_level"]),
                rank=int(case["rank"]),
                confidence=float(case["confidence"]),
                evidence_strength=float(case["evidence_strength"]),
                conflict_score=float(case["conflict_score"]),
                noise_type=str(case["noise_type"]),
                expected_decision=str(case["expected_decision"]),
                hop_depth=int(case.get("hop_depth", max_hop_depth)),
            )
            for case in definition.get("cases", [])
            if isinstance(case, dict)
        ]
        loaded.append(
            KnowledgeLevel(
                name=level_name,
                max_hop_depth=max_hop_depth,
                cases=cases,
                required_to_promote=bool(definition.get("required_to_promote", True)),
                description=str(definition.get("description", "")),
            )
        )
    return loaded


def validate_knowledge_level(
    level: KnowledgeLevel,
    *,
    known_knowledge_levels: set[str],
) -> KnowledgeGateResult:
    checked_case_ids: list[str] = []
    for case in level.cases:
        checked_case_ids.append(case.id)
        if case.hop_depth > level.max_hop_depth:
            return KnowledgeGateResult(
                level.name,
                False,
                checked_case_ids,
                level.max_hop_depth,
                f"{case.id} exceeds max hop depth",
            )
        if case.knowledge_level not in known_knowledge_levels:
            return KnowledgeGateResult(
                level.name,
                False,
                checked_case_ids,
                level.max_hop_depth,
                f"{case.id} unknown knowledge level {case.knowledge_level}",
            )
        actual = infer_knowledge_decision(case)
        if actual != case.expected_decision:
            return KnowledgeGateResult(
                level.name,
                False,
                checked_case_ids,
                level.max_hop_depth,
                f"{case.id} expected {case.expected_decision}, got {actual}",
            )
    return KnowledgeGateResult(level.name, True, checked_case_ids, level.max_hop_depth)


def run_knowledge_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[KnowledgeGateResult]:
    data = load_yaml(config_path)
    known_knowledge_levels = set(data.get("knowledge_levels", {}))
    results: list[KnowledgeGateResult] = []
    for level in load_knowledge_levels(config_path):
        result = validate_knowledge_level(
            level,
            known_knowledge_levels=known_knowledge_levels,
        )
        results.append(result)
        if level.name == max_level:
            break
        if level.required_to_promote and not result.passed:
            break
    return results

