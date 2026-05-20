from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class ToolComboCase:
    id: str
    flow: list[str]
    memory_layer: str
    tool: str
    provider: str
    noise_type: str
    expected_decision: str
    hop_depth: int


@dataclass(frozen=True)
class ToolComboLevel:
    name: str
    max_hop_depth: int
    cases: list[ToolComboCase]
    required_to_promote: bool
    description: str


@dataclass(frozen=True)
class ToolComboResult:
    level: str
    passed: bool
    checked_case_ids: list[str]
    max_hop_depth: int
    reason: str = ""


def parse_tool_combo_flow(flow: str) -> list[str]:
    return [stage.strip() for stage in flow.split("->") if stage.strip()]


def infer_tool_combo_decision(case: ToolComboCase, allowed_providers: set[str]) -> str:
    if case.noise_type == "deep_policy_shadowing":
        return "stop"
    if case.noise_type == "local_file_exfiltration_attempt":
        return "deny"
    if case.noise_type == "prompt_injection":
        return "quarantine"
    if case.noise_type == "stale_memory":
        return "verify"
    if case.noise_type == "seo_noise":
        return "verify_rank"
    if case.provider in allowed_providers:
        if case.noise_type == "provider_preference_noise":
            return "allow_if_provider_allowed"
        return "allow"
    return "deny"


def load_tool_combo_levels(config_path: Path) -> list[ToolComboLevel]:
    data = load_yaml(config_path)
    levels = data.get("tool_combo_gate_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid tool combo gate config in {config_path}"
        raise ValueError(msg)

    loaded: list[ToolComboLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        max_hop_depth = int(definition["max_hop_depth"])
        cases = [
            ToolComboCase(
                id=str(case["id"]),
                flow=parse_tool_combo_flow(str(case["flow"])),
                memory_layer=str(case["memory_layer"]),
                tool=str(case["tool"]),
                provider=str(case["provider"]),
                noise_type=str(case["noise_type"]),
                expected_decision=str(case["expected_decision"]),
                hop_depth=int(case.get("hop_depth", max_hop_depth)),
            )
            for case in definition.get("cases", [])
            if isinstance(case, dict)
        ]
        loaded.append(
            ToolComboLevel(
                name=level_name,
                max_hop_depth=max_hop_depth,
                cases=cases,
                required_to_promote=bool(definition.get("required_to_promote", True)),
                description=str(definition.get("description", "")),
            )
        )
    return loaded


def run_tool_combo_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[ToolComboResult]:
    data = load_yaml(config_path)
    allowed_providers = set(data["allowed_tools"]["web_search"]["providers"])
    results: list[ToolComboResult] = []
    for level in load_tool_combo_levels(config_path):
        checked: list[str] = []
        passed = True
        reason = ""
        for case in level.cases:
            checked.append(case.id)
            if case.hop_depth > level.max_hop_depth:
                passed = False
                reason = f"{case.id} exceeds max hop depth"
                break
            actual = infer_tool_combo_decision(case, allowed_providers)
            if actual != case.expected_decision:
                passed = False
                reason = f"{case.id} expected {case.expected_decision}, got {actual}"
                break
        result = ToolComboResult(level.name, passed, checked, level.max_hop_depth, reason)
        results.append(result)
        if level.name == max_level:
            break
        if level.required_to_promote and not passed:
            break
    return results

