from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.memory_layer_gate import (
    load_memory_layer_levels,
    run_memory_layer_promotion,
)


ROOT = Path(__file__).resolve().parents[2]


def test_memory_layer_levels_promote_to_hop_20() -> None:
    levels = load_memory_layer_levels(ROOT / "configs" / "memory_layer_gates.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert [level.max_hop_depth for level in levels] == [2, 5, 10, 20]


def test_memory_layers_m0_to_m5_are_defined() -> None:
    data = load_yaml(ROOT / "configs" / "memory_layer_gates.yaml")

    assert list(data["memory_layers"]) == [
        "M0_SESSION_SCRATCH",
        "M1_PERSONAL_PREFERENCE",
        "M2_PROJECT_CONVENTION",
        "M3_CONFIRMED_DECISION",
        "M4_WORKFLOW_MEMORY",
        "M5_SAFETY_POLICY",
    ]


def test_memory_layer_promotion_passes_static_gate_definitions() -> None:
    results = run_memory_layer_promotion(config_path=ROOT / "configs" / "memory_layer_gates.yaml")

    assert [result.level for result in results] == ["easy", "medium", "hard", "extreme"]
    assert all(result.passed for result in results)

