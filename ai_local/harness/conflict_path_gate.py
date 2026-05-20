from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class ConflictPath:
    id: str
    valid: bool


@dataclass(frozen=True)
class ConflictPathCase:
    id: str
    conflict_type: str
    paths: list[ConflictPath]
    forced_choice_required: bool
    expected_decision: str
    expected_path: str | None
    hop_depth: int


@dataclass(frozen=True)
class ConflictPathLevel:
    name: str
    max_hop_depth: int
    cases: list[ConflictPathCase]
    required_to_promote: bool
    description: str


@dataclass(frozen=True)
class ConflictPathResult:
    level: str
    passed: bool
    checked_case_ids: list[str]
    max_hop_depth: int
    reason: str = ""


def infer_conflict_decision(case: ConflictPathCase) -> tuple[str, str | None]:
    valid_paths = [path for path in case.paths if path.valid]
    if valid_paths:
        return "choose_path", valid_paths[0].id
    if case.conflict_type in {"destructive_tool_without_approval", "all_routes_unsafe"}:
        return "stop", None
    return "ask_user", None


def load_conflict_path_levels(config_path: Path) -> list[ConflictPathLevel]:
    data = load_yaml(config_path)
    levels = data.get("conflict_path_gate_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid conflict path config in {config_path}"
        raise ValueError(msg)

    loaded: list[ConflictPathLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        max_hop_depth = int(definition["max_hop_depth"])
        cases = [
            ConflictPathCase(
                id=str(case["id"]),
                conflict_type=str(case["conflict_type"]),
                paths=[
                    ConflictPath(id=str(path["id"]), valid=bool(path["valid"]))
                    for path in case.get("paths", [])
                    if isinstance(path, dict)
                ],
                forced_choice_required=bool(case["forced_choice_required"]),
                expected_decision=str(case["expected_decision"]),
                expected_path=str(case["expected_path"]) if "expected_path" in case else None,
                hop_depth=int(case.get("hop_depth", max_hop_depth)),
            )
            for case in definition.get("cases", [])
            if isinstance(case, dict)
        ]
        loaded.append(
            ConflictPathLevel(
                name=level_name,
                max_hop_depth=max_hop_depth,
                cases=cases,
                required_to_promote=bool(definition.get("required_to_promote", True)),
                description=str(definition.get("description", "")),
            )
        )
    return loaded


def validate_conflict_path_level(level: ConflictPathLevel) -> ConflictPathResult:
    checked_case_ids: list[str] = []
    for case in level.cases:
        checked_case_ids.append(case.id)
        if case.hop_depth > level.max_hop_depth:
            return ConflictPathResult(
                level.name,
                False,
                checked_case_ids,
                level.max_hop_depth,
                f"{case.id} exceeds max hop depth",
            )
        decision, path = infer_conflict_decision(case)
        if decision != case.expected_decision:
            return ConflictPathResult(
                level.name,
                False,
                checked_case_ids,
                level.max_hop_depth,
                f"{case.id} expected {case.expected_decision}, got {decision}",
            )
        if path != case.expected_path:
            return ConflictPathResult(
                level.name,
                False,
                checked_case_ids,
                level.max_hop_depth,
                f"{case.id} expected path {case.expected_path}, got {path}",
            )
    return ConflictPathResult(level.name, True, checked_case_ids, level.max_hop_depth)


def run_conflict_path_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[ConflictPathResult]:
    results: list[ConflictPathResult] = []
    for level in load_conflict_path_levels(config_path):
        result = validate_conflict_path_level(level)
        results.append(result)
        if level.name == max_level:
            break
        if level.required_to_promote and not result.passed:
            break
    return results

