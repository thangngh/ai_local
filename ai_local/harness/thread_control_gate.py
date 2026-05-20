from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class ThreadControlCase:
    id: str
    flow: list[str]
    control_event: str
    authority: str
    conflict_type: str
    expected_decision: str
    hop_depth: int


@dataclass(frozen=True)
class ThreadControlLevel:
    name: str
    max_hop_depth: int
    cases: list[ThreadControlCase]
    required_to_promote: bool
    description: str


@dataclass(frozen=True)
class ThreadControlResult:
    level: str
    passed: bool
    checked_case_ids: list[str]
    max_hop_depth: int
    reason: str = ""


def parse_thread_flow(flow: str) -> list[str]:
    return [stage.strip() for stage in flow.split("->") if stage.strip()]


def infer_thread_control_decision(case: ThreadControlCase) -> str:
    if case.conflict_type == "none" and case.authority == "current_user":
        return {
            "pause": "pause_thread",
            "resume": "resume_thread",
            "interrupt": "interrupt_thread",
            "archive": "archive_thread",
        }.get(case.control_event, "ask_user")
    if case.conflict_type == "stale_context":
        return "supersede_old_thread_step"
    if case.conflict_type == "duplicate_side_effect":
        return "dispatch_once"
    if case.conflict_type == "prompt_injection_control":
        return "refuse_control_event"
    if case.conflict_type in {"invalid_thread_state", "all_paths_invalid"}:
        return "stop"
    if case.conflict_type in {
        "stale_memory_vs_current_user",
        "unresolved_equivalence_class",
        "multi_instance_tie",
    }:
        return "ask_user"
    return "ask_user"


def load_thread_control_levels(config_path: Path) -> list[ThreadControlLevel]:
    data = load_yaml(config_path)
    levels = data.get("thread_control_gate_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid thread control config in {config_path}"
        raise ValueError(msg)

    loaded: list[ThreadControlLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        max_hop_depth = int(definition["max_hop_depth"])
        cases = [
            ThreadControlCase(
                id=str(case["id"]),
                flow=parse_thread_flow(str(case["flow"])),
                control_event=str(case["control_event"]),
                authority=str(case["authority"]),
                conflict_type=str(case["conflict_type"]),
                expected_decision=str(case["expected_decision"]),
                hop_depth=int(case.get("hop_depth", max_hop_depth)),
            )
            for case in definition.get("cases", [])
            if isinstance(case, dict)
        ]
        loaded.append(
            ThreadControlLevel(
                name=level_name,
                max_hop_depth=max_hop_depth,
                cases=cases,
                required_to_promote=bool(definition.get("required_to_promote", True)),
                description=str(definition.get("description", "")),
            )
        )
    return loaded


def run_thread_control_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[ThreadControlResult]:
    data = load_yaml(config_path)
    known_modules = set(data.get("thread_control_modules", []))
    authority_policy = data.get("authority_policy", {})
    results: list[ThreadControlResult] = []
    for level in load_thread_control_levels(config_path):
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
                reason = f"{case.id} has unknown thread modules: {unknown}"
                break
            if case.authority not in authority_policy:
                passed = False
                reason = f"{case.id} has unknown authority: {case.authority}"
                break
            actual = infer_thread_control_decision(case)
            if actual != case.expected_decision:
                passed = False
                reason = f"{case.id} expected {case.expected_decision}, got {actual}"
                break
        result = ThreadControlResult(level.name, passed, checked, level.max_hop_depth, reason)
        results.append(result)
        if level.name == max_level:
            break
        if level.required_to_promote and not passed:
            break
    return results
