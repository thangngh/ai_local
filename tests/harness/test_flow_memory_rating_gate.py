from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.flow_memory_rating_gate import (
    FlowMemoryRatingCase,
    infer_flow_memory_rating_decision,
    load_flow_memory_rating_levels,
    run_flow_memory_rating_promotion,
)


ROOT = Path(__file__).resolve().parents[2]


def test_flow_memory_rating_levels_scale_to_hop_50() -> None:
    levels = load_flow_memory_rating_levels(ROOT / "configs" / "flow_memory_rating_gates.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert [level.max_hop_depth for level in levels] == [6, 15, 30, 50]


def test_flow_memory_rating_promotion_passes() -> None:
    results = run_flow_memory_rating_promotion(
        config_path=ROOT / "configs" / "flow_memory_rating_gates.yaml"
    )

    assert all(result.passed for result in results)


def test_flow_memory_gate_tracks_role_and_flow() -> None:
    data = load_yaml(ROOT / "configs" / "flow_memory_rating_gates.yaml")

    assert "ROLE_BINDING" in data["flow_memory_modules"]
    assert "FLOW_MATCH" in data["flow_memory_modules"]
    assert "INTERFERENCE_SCORE" in data["flow_memory_modules"]


def test_wrong_flow_interference_is_downranked() -> None:
    case = FlowMemoryRatingCase(
        id="unit",
        flow=["MEMORY_RETRIEVAL", "FLOW_MATCH", "INTERFERENCE_SCORE", "RERANK"],
        scenario="wrong_flow_interference",
        expected_decision="downrank_interference",
        hop_depth=30,
    )

    assert infer_flow_memory_rating_decision(case) == "downrank_interference"
