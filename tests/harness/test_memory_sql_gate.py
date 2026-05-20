from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.memory_sql_gate import (
    MemorySqlCase,
    infer_memory_sql_decision,
    load_memory_sql_levels,
    run_memory_sql_promotion,
)


ROOT = Path(__file__).resolve().parents[2]


def test_memory_sql_levels_scale_to_hop_50() -> None:
    levels = load_memory_sql_levels(ROOT / "configs" / "memory_sql_gates.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert [level.max_hop_depth for level in levels] == [5, 12, 25, 50]


def test_memory_sql_promotion_passes_all_levels() -> None:
    results = run_memory_sql_promotion(config_path=ROOT / "configs" / "memory_sql_gates.yaml")

    assert [result.level for result in results] == ["easy", "medium", "hard", "extreme"]
    assert all(result.passed for result in results)


def test_memory_sql_schema_defines_core_tables() -> None:
    data = load_yaml(ROOT / "configs" / "memory_sql_gates.yaml")

    assert set(data["schema"]) == {
        "memory_items",
        "memory_evidence",
        "memory_conflicts",
        "memory_updates",
        "memory_usage",
    }
    assert data["max_supported_hop_depth"] == 50


def test_deep_memory_poisoning_quarantines() -> None:
    case = MemorySqlCase(
        id="unit",
        flow=["memory_candidate", "decision_gate"],
        memory_layer="M3_CONFIRMED_DECISION",
        required_tables=["memory_items"],
        noise_type="deep_memory_poisoning",
        expected_decision="quarantine",
        hop_depth=50,
    )

    assert infer_memory_sql_decision(case) == "quarantine"

