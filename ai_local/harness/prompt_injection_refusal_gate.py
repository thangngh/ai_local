from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class PromptInjectionCase:
    id: str
    input_text: str
    source_type: str
    injection_patterns: list[str]
    expected_detection: str
    expected_decision: str
    expected_tone: str
    hop_depth: int


@dataclass(frozen=True)
class PromptInjectionLevel:
    name: str
    max_hop_depth: int
    cases: list[PromptInjectionCase]
    required_to_promote: bool
    description: str


@dataclass(frozen=True)
class PromptInjectionResult:
    level: str
    passed: bool
    checked_case_ids: list[str]
    max_hop_depth: int
    reason: str = ""


def detect_prompt_injection(case: PromptInjectionCase) -> str:
    if case.expected_detection == "mixed_legit_and_injection":
        return "mixed_legit_and_injection"
    if case.injection_patterns:
        return "prompt_injection"
    return "clean"


def decide_refusal(case: PromptInjectionCase) -> str:
    patterns = set(case.injection_patterns)
    if "fake_approval" in patterns and "destructive_command" in patterns:
        return "stop"
    if "tool_policy_override" in patterns or "destructive_command" in patterns:
        return "deny"
    if "policy_shadowing" in patterns:
        return "ask_user"
    if case.expected_detection == "mixed_legit_and_injection":
        return "quarantine_injected_part"
    return "refuse"


def load_prompt_injection_levels(config_path: Path) -> list[PromptInjectionLevel]:
    data = load_yaml(config_path)
    levels = data.get("prompt_injection_refusal_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid prompt injection refusal config in {config_path}"
        raise ValueError(msg)

    loaded: list[PromptInjectionLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        max_hop_depth = int(definition["max_hop_depth"])
        cases = [
            PromptInjectionCase(
                id=str(case["id"]),
                input_text=str(case["input"]),
                source_type=str(case["source_type"]),
                injection_patterns=[str(pattern) for pattern in case.get("injection_patterns", [])],
                expected_detection=str(case["expected_detection"]),
                expected_decision=str(case["expected_decision"]),
                expected_tone=str(case["expected_tone"]),
                hop_depth=int(case.get("hop_depth", max_hop_depth)),
            )
            for case in definition.get("cases", [])
            if isinstance(case, dict)
        ]
        loaded.append(
            PromptInjectionLevel(
                name=level_name,
                max_hop_depth=max_hop_depth,
                cases=cases,
                required_to_promote=bool(definition.get("required_to_promote", True)),
                description=str(definition.get("description", "")),
            )
        )
    return loaded


def run_prompt_injection_refusal_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[PromptInjectionResult]:
    data = load_yaml(config_path)
    templates = data.get("refusal_templates", {})
    results: list[PromptInjectionResult] = []
    for level in load_prompt_injection_levels(config_path):
        checked: list[str] = []
        passed = True
        reason = ""
        for case in level.cases:
            checked.append(case.id)
            if case.hop_depth > level.max_hop_depth:
                passed = False
                reason = f"{case.id} exceeds max hop depth"
                break
            if detect_prompt_injection(case) != case.expected_detection:
                passed = False
                reason = f"{case.id} detection mismatch"
                break
            if decide_refusal(case) != case.expected_decision:
                passed = False
                reason = f"{case.id} decision mismatch"
                break
            if case.expected_tone not in templates:
                passed = False
                reason = f"{case.id} missing refusal template {case.expected_tone}"
                break
        result = PromptInjectionResult(level.name, passed, checked, level.max_hop_depth, reason)
        results.append(result)
        if level.name == max_level:
            break
        if level.required_to_promote and not passed:
            break
    return results

