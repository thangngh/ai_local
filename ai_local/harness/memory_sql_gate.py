from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class MemorySqlCase:
    id: str
    flow: list[str]
    memory_layer: str
    required_tables: list[str]
    noise_type: str
    expected_decision: str
    hop_depth: int


@dataclass(frozen=True)
class MemorySqlLevel:
    name: str
    max_hop_depth: int
    cases: list[MemorySqlCase]
    required_to_promote: bool
    description: str


@dataclass(frozen=True)
class MemorySqlResult:
    level: str
    passed: bool
    checked_case_ids: list[str]
    max_hop_depth: int
    reason: str = ""


def parse_memory_sql_flow(flow: str) -> list[str]:
    return [stage.strip() for stage in flow.split("->") if stage.strip()]


def infer_memory_sql_decision(case: MemorySqlCase) -> str:
    if case.noise_type == "deep_memory_poisoning":
        return "quarantine"
    if case.noise_type == "safety_policy_laundering":
        return "stop"
    if case.noise_type in {"inferred_policy", "conflicting_memory"}:
        return "ask_user"
    if case.noise_type == "stale_source_hash":
        return "demote"
    if case.noise_type == "wrong_scope":
        return "drop"
    if case.noise_type == "weak_project_evidence":
        return "verify"
    if case.noise_type == "scope_noise":
        return "reject_policy_promotion"
    return "accept"


def load_memory_sql_levels(config_path: Path) -> list[MemorySqlLevel]:
    data = load_yaml(config_path)
    levels = data.get("memory_sql_gate_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid memory SQL gate config in {config_path}"
        raise ValueError(msg)

    loaded: list[MemorySqlLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        max_hop_depth = int(definition["max_hop_depth"])
        cases = [
            MemorySqlCase(
                id=str(case["id"]),
                flow=parse_memory_sql_flow(str(case["flow"])),
                memory_layer=str(case["memory_layer"]),
                required_tables=[str(table) for table in case.get("required_tables", [])],
                noise_type=str(case["noise_type"]),
                expected_decision=str(case["expected_decision"]),
                hop_depth=int(case.get("hop_depth", max_hop_depth)),
            )
            for case in definition.get("cases", [])
            if isinstance(case, dict)
        ]
        loaded.append(
            MemorySqlLevel(
                name=level_name,
                max_hop_depth=max_hop_depth,
                cases=cases,
                required_to_promote=bool(definition.get("required_to_promote", True)),
                description=str(definition.get("description", "")),
            )
        )
    return loaded


def run_memory_sql_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[MemorySqlResult]:
    data = load_yaml(config_path)
    schema = data.get("schema", {})
    known_tables = set(schema) if isinstance(schema, dict) else set()
    results: list[MemorySqlResult] = []
    for level in load_memory_sql_levels(config_path):
        checked: list[str] = []
        passed = True
        reason = ""
        for case in level.cases:
            checked.append(case.id)
            if case.hop_depth > level.max_hop_depth:
                passed = False
                reason = f"{case.id} exceeds max hop depth"
                break
            missing_tables = [table for table in case.required_tables if table not in known_tables]
            if missing_tables:
                passed = False
                reason = f"{case.id} missing schema tables: {missing_tables}"
                break
            actual = infer_memory_sql_decision(case)
            if actual != case.expected_decision:
                passed = False
                reason = f"{case.id} expected {case.expected_decision}, got {actual}"
                break
        result = MemorySqlResult(level.name, passed, checked, level.max_hop_depth, reason)
        results.append(result)
        if level.name == max_level:
            break
        if level.required_to_promote and not passed:
            break
    return results

