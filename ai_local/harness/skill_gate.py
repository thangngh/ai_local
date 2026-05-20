from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.skills.loader import parse_skill_markdown


@dataclass(frozen=True)
class SkillGateCase:
    id: str
    flow: list[str]
    skill_id: str
    noise_type: str
    expected_decision: str
    hop_depth: int
    requested_tool: str | None


@dataclass(frozen=True)
class SkillGateLevel:
    name: str
    max_hop_depth: int
    cases: list[SkillGateCase]
    required_to_promote: bool
    description: str


@dataclass(frozen=True)
class SkillGateResult:
    level: str
    passed: bool
    checked_case_ids: list[str]
    max_hop_depth: int
    reason: str = ""


def parse_skill_flow(flow: str) -> list[str]:
    return [stage.strip() for stage in flow.split("->") if stage.strip()]


def infer_skill_decision(
    case: SkillGateCase,
    *,
    registered_skill_tools: dict[str, set[str]],
    trusted_skills: dict[str, bool],
) -> str:
    if case.noise_type == "deep_policy_shadowing":
        return "stop"
    if case.noise_type == "prompt_injection":
        return "quarantine"
    if case.noise_type == "unlisted_tool_request":
        allowed = registered_skill_tools.get(case.skill_id, set())
        return "allow" if case.requested_tool in allowed else "deny"
    if case.noise_type == "untrusted_policy_write" and not trusted_skills.get(case.skill_id, False):
        return "ask_user"
    if case.noise_type == "seo_noise":
        return "verify_rank"
    if case.noise_type in {"weak_evidence", "deep_weak_evidence"}:
        return "verify_more" if case.noise_type == "weak_evidence" else "ask_user"
    return "allow"


def load_skill_gate_levels(config_path: Path) -> list[SkillGateLevel]:
    data = load_yaml(config_path)
    levels = data.get("skill_gate_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid skill gate config in {config_path}"
        raise ValueError(msg)
    loaded: list[SkillGateLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        max_hop_depth = int(definition["max_hop_depth"])
        cases = [
            SkillGateCase(
                id=str(case["id"]),
                flow=parse_skill_flow(str(case["flow"])),
                skill_id=str(case["skill_id"]),
                noise_type=str(case["noise_type"]),
                expected_decision=str(case["expected_decision"]),
                hop_depth=int(case.get("hop_depth", max_hop_depth)),
                requested_tool=str(case["requested_tool"]) if "requested_tool" in case else None,
            )
            for case in definition.get("cases", [])
            if isinstance(case, dict)
        ]
        loaded.append(
            SkillGateLevel(
                name=level_name,
                max_hop_depth=max_hop_depth,
                cases=cases,
                required_to_promote=bool(definition.get("required_to_promote", True)),
                description=str(definition.get("description", "")),
            )
        )
    return loaded


def run_skill_promotion(
    *,
    config_path: Path,
    root: Path,
    max_level: str | None = None,
) -> list[SkillGateResult]:
    data = load_yaml(config_path)
    registered = data.get("registered_skills", {})
    if not isinstance(registered, dict):
        return []
    registered_skill_tools: dict[str, set[str]] = {}
    trusted_skills: dict[str, bool] = {}
    for skill_id, definition in registered.items():
        if not isinstance(skill_id, str) or not isinstance(definition, dict):
            continue
        skill_path = root / str(definition["path"])
        skill = parse_skill_markdown(skill_path)
        registered_skill_tools[skill_id] = set(skill.allowed_tools)
        trusted_skills[skill_id] = skill.trusted

    results: list[SkillGateResult] = []
    for level in load_skill_gate_levels(config_path):
        checked: list[str] = []
        passed = True
        reason = ""
        for case in level.cases:
            checked.append(case.id)
            if case.hop_depth > level.max_hop_depth:
                passed = False
                reason = f"{case.id} exceeds max hop depth"
                break
            actual = infer_skill_decision(
                case,
                registered_skill_tools=registered_skill_tools,
                trusted_skills=trusted_skills,
            )
            if actual != case.expected_decision:
                passed = False
                reason = f"{case.id} expected {case.expected_decision}, got {actual}"
                break
        result = SkillGateResult(level.name, passed, checked, level.max_hop_depth, reason)
        results.append(result)
        if level.name == max_level:
            break
        if level.required_to_promote and not passed:
            break
    return results

