from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class ConfirmationCase:
    id: str
    flow: list[str]
    trigger: str
    noise_type: str
    expected_decision: str
    hop_depth: int


@dataclass(frozen=True)
class ConfirmationLevel:
    name: str
    max_hop_depth: int
    cases: list[ConfirmationCase]
    required_to_promote: bool
    description: str


@dataclass(frozen=True)
class ConfirmationGateResult:
    level: str
    passed: bool
    checked_case_ids: list[str]
    max_hop_depth: int
    reason: str = ""


def parse_confirmation_flow(flow: str) -> list[str]:
    return [stage.strip() for stage in flow.split("->") if stage.strip()]


def infer_confirmation_decision(case: ConfirmationCase) -> str:
    if case.noise_type == "fake_approval_laundering":
        return "stop"
    if case.noise_type == "prompt_injected_options":
        return "quarantine"
    if case.trigger == "technical_risk":
        return "ask_tech_lead"
    if case.trigger == "dangerous_action":
        return "require_approval"
    if case.trigger == "conflicting_answer":
        return "ask_user"
    if case.trigger == "confirmed_policy":
        return "save_policy_and_resume"
    if case.trigger == "safety_policy":
        return "save_policy_not_preference"
    if "OPTIONS_WITH_IMPACT" in case.flow:
        return "wait_for_user"
    return "ask_user"


def load_confirmation_levels(config_path: Path) -> list[ConfirmationLevel]:
    data = load_yaml(config_path)
    levels = data.get("confirmation_gate_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid confirmation gate config in {config_path}"
        raise ValueError(msg)

    loaded: list[ConfirmationLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        max_hop_depth = int(definition["max_hop_depth"])
        cases = [
            ConfirmationCase(
                id=str(case["id"]),
                flow=parse_confirmation_flow(str(case["flow"])),
                trigger=str(case["trigger"]),
                noise_type=str(case["noise_type"]),
                expected_decision=str(case["expected_decision"]),
                hop_depth=int(case.get("hop_depth", max_hop_depth)),
            )
            for case in definition.get("cases", [])
            if isinstance(case, dict)
        ]
        loaded.append(
            ConfirmationLevel(
                name=level_name,
                max_hop_depth=max_hop_depth,
                cases=cases,
                required_to_promote=bool(definition.get("required_to_promote", True)),
                description=str(definition.get("description", "")),
            )
        )
    return loaded


def validate_confirmation_level(level: ConfirmationLevel) -> ConfirmationGateResult:
    checked_case_ids: list[str] = []
    for case in level.cases:
        checked_case_ids.append(case.id)
        if case.hop_depth > level.max_hop_depth:
            return ConfirmationGateResult(
                level.name,
                False,
                checked_case_ids,
                level.max_hop_depth,
                f"{case.id} exceeds max hop depth",
            )
        actual = infer_confirmation_decision(case)
        if actual != case.expected_decision:
            return ConfirmationGateResult(
                level.name,
                False,
                checked_case_ids,
                level.max_hop_depth,
                f"{case.id} expected {case.expected_decision}, got {actual}",
            )
    return ConfirmationGateResult(level.name, True, checked_case_ids, level.max_hop_depth)


def run_confirmation_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[ConfirmationGateResult]:
    results: list[ConfirmationGateResult] = []
    for level in load_confirmation_levels(config_path):
        result = validate_confirmation_level(level)
        results.append(result)
        if level.name == max_level:
            break
        if level.required_to_promote and not result.passed:
            break
    return results

