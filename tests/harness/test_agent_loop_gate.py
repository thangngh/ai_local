from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.agent_loop_gate import (
    AgentLoopCase,
    infer_agent_loop_decision,
    load_agent_loop_levels,
    parse_flow,
    run_agent_loop_promotion,
)


ROOT = Path(__file__).resolve().parents[2]


def test_agent_loop_levels_prioritize_deep_core_hops() -> None:
    levels = load_agent_loop_levels(ROOT / "configs" / "agent_loop_gates.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert [level.max_hop_depth for level in levels] == [5, 12, 25, 50]


def test_agent_loop_promotion_passes_all_levels() -> None:
    results = run_agent_loop_promotion(config_path=ROOT / "configs" / "agent_loop_gates.yaml")

    assert [result.level for result in results] == ["easy", "medium", "hard", "extreme"]
    assert all(result.passed for result in results)


def test_agent_loop_core_states_match_notion_flow() -> None:
    data = load_yaml(ROOT / "configs" / "agent_loop_gates.yaml")
    core_states = data["state_policy"]["required_core_states"]

    assert core_states[0] == "INTAKE"
    assert "DECISION_GATE" in core_states
    assert data["noise_policy"]["max_supported_hop_depth"] == 50


def test_parse_flow_handles_state_arrow_syntax() -> None:
    assert parse_flow("INTAKE -> PLAN -> PLAN_GATE") == ["INTAKE", "PLAN", "PLAN_GATE"]


def test_deep_prompt_shadowing_rolls_back() -> None:
    case = AgentLoopCase(
        id="unit",
        flow=["INTAKE", "PLAN", "DECISION_GATE"],
        expected_terminal="ROLLBACK",
        noise_type="deep_prompt_shadowing",
        expected_decision="rollback",
        hop_depth=50,
    )

    assert infer_agent_loop_decision(case) == "rollback"

