from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class VibeAgentDebugScenario:
    id: str
    project: str
    query: str
    noise_profile: str
    conflict_profile: str
    hop_depth: int
    expected_route: str
    safe_intervention: str
    blocked_intervention: str


@dataclass(frozen=True)
class VibeAgentDebugPlan:
    target_root: str
    ollama_model: str
    index_root: str
    scenarios: list[VibeAgentDebugScenario]


def load_vibe_agent_debug_plan(config_path: Path) -> VibeAgentDebugPlan:
    data = load_yaml(config_path)
    scenarios = [
        VibeAgentDebugScenario(
            id=str(item["id"]),
            project=str(item["project"]),
            query=str(item["query"]),
            noise_profile=str(item["noise_profile"]),
            conflict_profile=str(item["conflict_profile"]),
            hop_depth=int(item["hop_depth"]),
            expected_route=str(item["expected_route"]),
            safe_intervention=str(item["safe_intervention"]),
            blocked_intervention=str(item["blocked_intervention"]),
        )
        for item in data.get("scenarios", [])
        if isinstance(item, dict)
    ]
    return VibeAgentDebugPlan(
        target_root=str(data["target_root"]),
        ollama_model=str(data["ollama_model"]),
        index_root=str(data["index_root"]),
        scenarios=scenarios,
    )


def validate_vibe_agent_debug_plan(plan: VibeAgentDebugPlan) -> list[str]:
    errors: list[str] = []
    if plan.ollama_model != "qwen2.5:0.5b":
        errors.append("ollama model must be qwen2.5:0.5b")
    if len(plan.scenarios) < 10:
        errors.append("at least 10 debug conflict scenarios are required")
    if not any(scenario.hop_depth >= 50 for scenario in plan.scenarios):
        errors.append("at least one no-path or extreme scenario must reach hop depth 50")
    if not any(scenario.noise_profile == "prompt_injection" for scenario in plan.scenarios):
        errors.append("prompt injection noise scenario is required")
    if not any(scenario.conflict_profile == "no_path" for scenario in plan.scenarios):
        errors.append("no-path conflict scenario is required")
    for scenario in plan.scenarios:
        if scenario.hop_depth <= 0:
            errors.append(f"{scenario.id}: hop depth must be positive")
        if not scenario.safe_intervention:
            errors.append(f"{scenario.id}: safe intervention is required")
        if not scenario.blocked_intervention:
            errors.append(f"{scenario.id}: blocked intervention is required")
    return errors
