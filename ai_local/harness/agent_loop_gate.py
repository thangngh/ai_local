from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class AgentLoopCase:
    id: str
    flow: list[str]
    expected_terminal: str
    noise_type: str
    expected_decision: str
    hop_depth: int


@dataclass(frozen=True)
class AgentLoopLevel:
    name: str
    max_hop_depth: int
    cases: list[AgentLoopCase]
    required_to_promote: bool
    description: str


@dataclass(frozen=True)
class AgentLoopGateResult:
    level: str
    passed: bool
    checked_case_ids: list[str]
    max_hop_depth: int
    reason: str = ""


def parse_flow(flow: str) -> list[str]:
    return [state.strip() for state in flow.split("->") if state.strip()]


def infer_agent_loop_decision(case: AgentLoopCase) -> str:
    if case.noise_type == "deep_prompt_shadowing":
        return "rollback"
    if case.noise_type in {"ambiguity", "missing_business_info", "memory_retrieval_interference"}:
        return "ask_user"
    if case.noise_type == "weak_context":
        return "retrieve_more"
    if case.noise_type == "risky_patch":
        return "ask_tech_lead"
    if case.noise_type == "bad_patch":
        return "retry"
    if case.noise_type == "serious_test_failure":
        return "rollback"
    if case.expected_terminal == "DONE":
        return "done"
    return "continue"


def load_agent_loop_levels(config_path: Path) -> list[AgentLoopLevel]:
    data = load_yaml(config_path)
    levels = data.get("agent_loop_gate_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid agent loop gate config in {config_path}"
        raise ValueError(msg)

    loaded: list[AgentLoopLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        max_hop_depth = int(definition["max_hop_depth"])
        cases = [
            AgentLoopCase(
                id=str(case["id"]),
                flow=parse_flow(str(case["flow"])),
                expected_terminal=str(case["expected_terminal"]),
                noise_type=str(case["noise_type"]),
                expected_decision=str(case["expected_decision"]),
                hop_depth=int(case.get("hop_depth", max_hop_depth)),
            )
            for case in definition.get("cases", [])
            if isinstance(case, dict)
        ]
        loaded.append(
            AgentLoopLevel(
                name=level_name,
                max_hop_depth=max_hop_depth,
                cases=cases,
                required_to_promote=bool(definition.get("required_to_promote", True)),
                description=str(definition.get("description", "")),
            )
        )
    return loaded


def validate_agent_loop_level(
    level: AgentLoopLevel,
    *,
    known_states: set[str],
) -> AgentLoopGateResult:
    checked_case_ids: list[str] = []
    for case in level.cases:
        checked_case_ids.append(case.id)
        if case.hop_depth > level.max_hop_depth:
            return AgentLoopGateResult(
                level=level.name,
                passed=False,
                checked_case_ids=checked_case_ids,
                max_hop_depth=level.max_hop_depth,
                reason=f"{case.id} exceeds max hop depth",
            )
        unknown_states = [state for state in case.flow if state not in known_states]
        if unknown_states:
            return AgentLoopGateResult(
                level=level.name,
                passed=False,
                checked_case_ids=checked_case_ids,
                max_hop_depth=level.max_hop_depth,
                reason=f"{case.id} has unknown states: {unknown_states}",
            )
        if case.expected_terminal not in known_states:
            return AgentLoopGateResult(
                level=level.name,
                passed=False,
                checked_case_ids=checked_case_ids,
                max_hop_depth=level.max_hop_depth,
                reason=f"{case.id} has unknown terminal {case.expected_terminal}",
            )
        actual_decision = infer_agent_loop_decision(case)
        if actual_decision != case.expected_decision:
            return AgentLoopGateResult(
                level=level.name,
                passed=False,
                checked_case_ids=checked_case_ids,
                max_hop_depth=level.max_hop_depth,
                reason=f"{case.id} expected {case.expected_decision}, got {actual_decision}",
            )
    return AgentLoopGateResult(
        level=level.name,
        passed=True,
        checked_case_ids=checked_case_ids,
        max_hop_depth=level.max_hop_depth,
    )


def run_agent_loop_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[AgentLoopGateResult]:
    data = load_yaml(config_path)
    state_policy = data.get("state_policy", {})
    if not isinstance(state_policy, dict):
        msg = f"Invalid state policy in {config_path}"
        raise ValueError(msg)
    known_states = {
        str(state)
        for key in ("terminal_states", "retry_states", "required_core_states")
        for state in state_policy.get(key, [])
    }
    known_states.add(str(state_policy.get("start_state", "INTAKE")))

    results: list[AgentLoopGateResult] = []
    for level in load_agent_loop_levels(config_path):
        result = validate_agent_loop_level(level, known_states=known_states)
        results.append(result)
        if level.name == max_level:
            break
        if level.required_to_promote and not result.passed:
            break
    return results

