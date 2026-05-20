from pathlib import Path

from ai_local.harness.skill_gate import (
    SkillGateCase,
    infer_skill_decision,
    load_skill_gate_levels,
    run_skill_promotion,
)


ROOT = Path(__file__).resolve().parents[2]


def test_skill_gate_levels_scale_to_hop_50() -> None:
    levels = load_skill_gate_levels(ROOT / "configs" / "skill_gates.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert [level.max_hop_depth for level in levels] == [5, 12, 25, 50]


def test_skill_promotion_passes_all_levels() -> None:
    results = run_skill_promotion(
        config_path=ROOT / "configs" / "skill_gates.yaml",
        root=ROOT,
    )

    assert [result.level for result in results] == ["easy", "medium", "hard", "extreme"]
    assert all(result.passed for result in results)


def test_unlisted_tool_request_is_denied() -> None:
    case = SkillGateCase(
        id="unit",
        flow=["skill", "tool_registry"],
        skill_id="web-research",
        noise_type="unlisted_tool_request",
        expected_decision="deny",
        hop_depth=1,
        requested_tool="filesystem.patch",
    )

    assert (
        infer_skill_decision(
            case,
            registered_skill_tools={"web-research": {"web_search"}},
            trusted_skills={"web-research": False},
        )
        == "deny"
    )

