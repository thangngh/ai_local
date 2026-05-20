from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class RequestLifecycleCase:
    id: str
    flow: list[str]
    conflict_type: str
    expected_decision: str
    hop_depth: int


@dataclass(frozen=True)
class RequestLifecycleLevel:
    name: str
    max_hop_depth: int
    cases: list[RequestLifecycleCase]
    required_to_promote: bool
    description: str


@dataclass(frozen=True)
class RequestLifecycleResult:
    level: str
    passed: bool
    checked_case_ids: list[str]
    max_hop_depth: int
    reason: str = ""


def parse_lifecycle_flow(flow: str) -> list[str]:
    return [stage.strip() for stage in flow.split("->") if stage.strip()]


def infer_lifecycle_decision(case: RequestLifecycleCase) -> str:
    mapping = {
        "none": "final_answer",
        "ambiguity": "ask_user",
        "fixable_failure": "retry",
        "knowledge_retrieval_conflict": "ask_user",
        "tool_policy_override": "quarantine",
        "patch_claim_vs_test_failure": "rollback",
        "duplicate_side_effect": "dispatch_once",
        "unresolved_equivalence_class": "ask_user",
        "all_paths_invalid": "stop",
    }
    return mapping.get(case.conflict_type, "ask_user")


def load_request_lifecycle_levels(config_path: Path) -> list[RequestLifecycleLevel]:
    data = load_yaml(config_path)
    levels = data.get("request_lifecycle_gate_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid request lifecycle config in {config_path}"
        raise ValueError(msg)

    loaded: list[RequestLifecycleLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        max_hop_depth = int(definition["max_hop_depth"])
        cases = [
            RequestLifecycleCase(
                id=str(case["id"]),
                flow=parse_lifecycle_flow(str(case["flow"])),
                conflict_type=str(case["conflict_type"]),
                expected_decision=str(case["expected_decision"]),
                hop_depth=int(case.get("hop_depth", max_hop_depth)),
            )
            for case in definition.get("cases", [])
            if isinstance(case, dict)
        ]
        loaded.append(
            RequestLifecycleLevel(
                name=level_name,
                max_hop_depth=max_hop_depth,
                cases=cases,
                required_to_promote=bool(definition.get("required_to_promote", True)),
                description=str(definition.get("description", "")),
            )
        )
    return loaded


def run_request_lifecycle_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[RequestLifecycleResult]:
    data = load_yaml(config_path)
    known_modules = set(data.get("lifecycle_modules", []))
    results: list[RequestLifecycleResult] = []
    for level in load_request_lifecycle_levels(config_path):
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
                reason = f"{case.id} has unknown lifecycle modules: {unknown}"
                break
            actual = infer_lifecycle_decision(case)
            if actual != case.expected_decision:
                passed = False
                reason = f"{case.id} expected {case.expected_decision}, got {actual}"
                break
        result = RequestLifecycleResult(level.name, passed, checked, level.max_hop_depth, reason)
        results.append(result)
        if level.name == max_level:
            break
        if level.required_to_promote and not passed:
            break
    return results

