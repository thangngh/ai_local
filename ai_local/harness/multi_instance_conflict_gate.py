from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class ConflictInstance:
    id: str
    evidence_rank: int
    risk: float
    authority: str


@dataclass(frozen=True)
class MultiInstanceConflictCase:
    id: str
    modules: list[str]
    instances: list[ConflictInstance]
    conflict_type: str
    expected_decision: str
    hop_depth: int


@dataclass(frozen=True)
class MultiInstanceConflictLevel:
    name: str
    max_hop_depth: int
    cases: list[MultiInstanceConflictCase]
    required_to_promote: bool
    description: str


@dataclass(frozen=True)
class MultiInstanceConflictResult:
    level: str
    passed: bool
    checked_case_ids: list[str]
    max_hop_depth: int
    reason: str = ""


def infer_multi_instance_decision(case: MultiInstanceConflictCase) -> str:
    if case.conflict_type in {"no_safe_path", "all_paths_invalid"}:
        return "stop"
    if case.conflict_type == "missing_test_evidence":
        return "defer_until_evidence"
    if case.conflict_type in {
        "equal_authority_equal_evidence",
        "multi_instance_tie",
        "circular_confirmation",
        "unresolved_equivalence_class",
    }:
        return "ask_user"
    return "ask_user"


def load_multi_instance_conflict_levels(config_path: Path) -> list[MultiInstanceConflictLevel]:
    data = load_yaml(config_path)
    levels = data.get("multi_instance_conflict_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid multi-instance conflict config in {config_path}"
        raise ValueError(msg)

    loaded: list[MultiInstanceConflictLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        max_hop_depth = int(definition["max_hop_depth"])
        cases = [
            MultiInstanceConflictCase(
                id=str(case["id"]),
                modules=[str(module) for module in case.get("modules", [])],
                instances=[
                    ConflictInstance(
                        id=str(instance["id"]),
                        evidence_rank=int(instance["evidence_rank"]),
                        risk=float(instance["risk"]),
                        authority=str(instance["authority"]),
                    )
                    for instance in case.get("instances", [])
                    if isinstance(instance, dict)
                ],
                conflict_type=str(case["conflict_type"]),
                expected_decision=str(case["expected_decision"]),
                hop_depth=int(case.get("hop_depth", max_hop_depth)),
            )
            for case in definition.get("cases", [])
            if isinstance(case, dict)
        ]
        loaded.append(
            MultiInstanceConflictLevel(
                name=level_name,
                max_hop_depth=max_hop_depth,
                cases=cases,
                required_to_promote=bool(definition.get("required_to_promote", True)),
                description=str(definition.get("description", "")),
            )
        )
    return loaded


def run_multi_instance_conflict_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[MultiInstanceConflictResult]:
    results: list[MultiInstanceConflictResult] = []
    for level in load_multi_instance_conflict_levels(config_path):
        checked: list[str] = []
        passed = True
        reason = ""
        for case in level.cases:
            checked.append(case.id)
            if case.hop_depth > level.max_hop_depth:
                passed = False
                reason = f"{case.id} exceeds max hop depth"
                break
            if len(case.instances) < 2:
                passed = False
                reason = f"{case.id} needs at least two conflicting instances"
                break
            actual = infer_multi_instance_decision(case)
            if actual != case.expected_decision:
                passed = False
                reason = f"{case.id} expected {case.expected_decision}, got {actual}"
                break
        result = MultiInstanceConflictResult(level.name, passed, checked, level.max_hop_depth, reason)
        results.append(result)
        if level.name == max_level:
            break
        if level.required_to_promote and not passed:
            break
    return results

