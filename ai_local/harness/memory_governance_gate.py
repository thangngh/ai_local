from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class MemoryGovernanceCase:
    id: str
    flow: list[str]
    scenario: str
    expected_decision: str
    hop_depth: int


@dataclass(frozen=True)
class MemoryGovernanceLevel:
    name: str
    max_hop_depth: int
    cases: list[MemoryGovernanceCase]
    required_to_promote: bool
    description: str


@dataclass(frozen=True)
class MemoryGovernanceResult:
    level: str
    passed: bool
    checked_case_ids: list[str]
    max_hop_depth: int
    reason: str = ""


def parse_memory_governance_flow(flow: str) -> list[str]:
    return [stage.strip() for stage in flow.split("->") if stage.strip()]


def infer_memory_governance_decision(case: MemoryGovernanceCase) -> str:
    decisions = {
        "strong_write_candidate": "accept_memory",
        "secret_candidate": "reject_memory",
        "strong_retrieval": "inject_memory",
        "stale_project_memory": "verify_before_use",
        "inferred_policy_candidate": "ask_user",
        "conflicted_memory": "do_not_use",
        "source_hash_changed": "demote_stale",
        "newer_confirmed_overrides_inferred": "prefer_confirmed_memory",
        "harmful_usage_history": "archive_memory",
    }
    return decisions.get(case.scenario, "ask_user")


def load_memory_governance_levels(config_path: Path) -> list[MemoryGovernanceLevel]:
    data = load_yaml(config_path)
    levels = data.get("memory_governance_gate_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid memory governance config in {config_path}"
        raise ValueError(msg)

    loaded: list[MemoryGovernanceLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        max_hop_depth = int(definition["max_hop_depth"])
        cases = [
            MemoryGovernanceCase(
                id=str(case["id"]),
                flow=parse_memory_governance_flow(str(case["flow"])),
                scenario=str(case["scenario"]),
                expected_decision=str(case["expected_decision"]),
                hop_depth=int(case.get("hop_depth", max_hop_depth)),
            )
            for case in definition.get("cases", [])
            if isinstance(case, dict)
        ]
        loaded.append(
            MemoryGovernanceLevel(
                name=level_name,
                max_hop_depth=max_hop_depth,
                cases=cases,
                required_to_promote=bool(definition.get("required_to_promote", True)),
                description=str(definition.get("description", "")),
            )
        )
    return loaded


def run_memory_governance_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[MemoryGovernanceResult]:
    data = load_yaml(config_path)
    known_modules = set(data.get("memory_governance_modules", []))
    results: list[MemoryGovernanceResult] = []
    for level in load_memory_governance_levels(config_path):
        checked: list[str] = []
        passed = True
        reason = ""
        for case in level.cases:
            checked.append(case.id)
            if case.hop_depth > level.max_hop_depth:
                passed = False
                reason = f"{case.id} exceeds max hop depth"
                break
            unknown = [stage for stage in case.flow if stage not in known_modules]
            if unknown:
                passed = False
                reason = f"{case.id} has unknown memory modules: {unknown}"
                break
            actual = infer_memory_governance_decision(case)
            if actual != case.expected_decision:
                passed = False
                reason = f"{case.id} expected {case.expected_decision}, got {actual}"
                break
        result = MemoryGovernanceResult(level.name, passed, checked, level.max_hop_depth, reason)
        results.append(result)
        if level.name == max_level:
            break
        if level.required_to_promote and not passed:
            break
    return results
