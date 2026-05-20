from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.tool_combo_gate import (
    ToolComboCase,
    infer_tool_combo_decision,
    load_tool_combo_levels,
    run_tool_combo_promotion,
)
from ai_local.tools.registry import ToolRegistry


ROOT = Path(__file__).resolve().parents[2]


def test_web_search_tool_registered_with_allowed_providers() -> None:
    data = load_yaml(ROOT / "configs" / "tools.yaml")
    registry = ToolRegistry.from_yaml(ROOT / "configs" / "tools.yaml")

    assert "web_search" in registry.names()
    assert data["tools"]["web_search"]["providers"]["allowed"] == ["duckduckgo", "bing"]


def test_tool_combo_levels_scale_to_hop_50() -> None:
    levels = load_tool_combo_levels(ROOT / "configs" / "tool_combo_gates.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert [level.max_hop_depth for level in levels] == [5, 12, 25, 50]


def test_tool_combo_promotion_passes_all_levels() -> None:
    results = run_tool_combo_promotion(config_path=ROOT / "configs" / "tool_combo_gates.yaml")

    assert [result.level for result in results] == ["easy", "medium", "hard", "extreme"]
    assert all(result.passed for result in results)


def test_memory_cannot_enable_local_file_access_for_web_search() -> None:
    case = ToolComboCase(
        id="unit",
        flow=["memory", "web_search"],
        memory_layer="M5_SAFETY_POLICY",
        tool="web_search",
        provider="duckduckgo",
        noise_type="local_file_exfiltration_attempt",
        expected_decision="deny",
        hop_depth=1,
    )

    assert infer_tool_combo_decision(case, {"duckduckgo", "bing"}) == "deny"

