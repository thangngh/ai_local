from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class EvidenceRankCase:
    id: str
    source_authority: int
    evidence_strength: int
    freshness: int
    project_relevance: int
    confirmation_weight: int
    conflict_penalty: int
    staleness_penalty: int
    noise_type: str
    expected_band: str
    hop_depth: int


@dataclass(frozen=True)
class EvidenceRankLevel:
    name: str
    max_hop_depth: int
    cases: list[EvidenceRankCase]
    required_to_promote: bool
    description: str


@dataclass(frozen=True)
class EvidenceRankResult:
    level: str
    passed: bool
    checked_case_ids: list[str]
    max_hop_depth: int
    reason: str = ""


def calculate_rank(case: EvidenceRankCase) -> int:
    return (
        case.source_authority
        + case.evidence_strength
        + case.freshness
        + case.project_relevance
        + case.confirmation_weight
        - case.conflict_penalty
        - case.staleness_penalty
    )


def rank_band(case: EvidenceRankCase) -> str:
    if case.noise_type in {"prompt_injection", "policy_laundering", "repeated_untrusted_claim"}:
        return "reject"
    rank = calculate_rank(case)
    if rank >= 90:
        return "canonical"
    if rank >= 75:
        return "strong"
    if rank >= 60:
        return "caution"
    if rank >= 40:
        return "weak"
    return "reject"


def load_evidence_rank_levels(config_path: Path) -> list[EvidenceRankLevel]:
    data = load_yaml(config_path)
    levels = data.get("evidence_rank_gate_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid evidence rank config in {config_path}"
        raise ValueError(msg)

    loaded: list[EvidenceRankLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        max_hop_depth = int(definition["max_hop_depth"])
        cases = [
            EvidenceRankCase(
                id=str(case["id"]),
                source_authority=int(case["source_authority"]),
                evidence_strength=int(case["evidence_strength"]),
                freshness=int(case["freshness"]),
                project_relevance=int(case["project_relevance"]),
                confirmation_weight=int(case["confirmation_weight"]),
                conflict_penalty=int(case["conflict_penalty"]),
                staleness_penalty=int(case["staleness_penalty"]),
                noise_type=str(case["noise_type"]),
                expected_band=str(case["expected_band"]),
                hop_depth=int(case.get("hop_depth", max_hop_depth)),
            )
            for case in definition.get("cases", [])
            if isinstance(case, dict)
        ]
        loaded.append(
            EvidenceRankLevel(
                name=level_name,
                max_hop_depth=max_hop_depth,
                cases=cases,
                required_to_promote=bool(definition.get("required_to_promote", True)),
                description=str(definition.get("description", "")),
            )
        )
    return loaded


def validate_evidence_rank_level(level: EvidenceRankLevel) -> EvidenceRankResult:
    checked_case_ids: list[str] = []
    for case in level.cases:
        checked_case_ids.append(case.id)
        if case.hop_depth > level.max_hop_depth:
            return EvidenceRankResult(
                level.name,
                False,
                checked_case_ids,
                level.max_hop_depth,
                f"{case.id} exceeds max hop depth",
            )
        actual = rank_band(case)
        if actual != case.expected_band:
            return EvidenceRankResult(
                level.name,
                False,
                checked_case_ids,
                level.max_hop_depth,
                f"{case.id} expected {case.expected_band}, got {actual}",
            )
    return EvidenceRankResult(level.name, True, checked_case_ids, level.max_hop_depth)


def run_evidence_rank_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[EvidenceRankResult]:
    results: list[EvidenceRankResult] = []
    for level in load_evidence_rank_levels(config_path):
        result = validate_evidence_rank_level(level)
        results.append(result)
        if level.name == max_level:
            break
        if level.required_to_promote and not result.passed:
            break
    return results

