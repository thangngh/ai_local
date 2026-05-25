from pathlib import Path

from ai_local.harness.vibe_agent_debug import (
    load_vibe_agent_debug_plan,
    validate_vibe_agent_debug_plan,
)


ROOT = Path(__file__).resolve().parents[2]


def test_vibe_agent_debug_plan_covers_conflict_noise_and_hop_depth() -> None:
    plan = load_vibe_agent_debug_plan(ROOT / "configs" / "vibe_agent_debug_scenarios.yaml")

    assert validate_vibe_agent_debug_plan(plan) == []
    assert len(plan.scenarios) == 10
    assert plan.ollama_model == "qwen2.5:0.5b"
    assert max(scenario.hop_depth for scenario in plan.scenarios) == 50
    assert {scenario.project for scenario in plan.scenarios} >= {
        "ddd",
        "monitor-software-main",
    }
