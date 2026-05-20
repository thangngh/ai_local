from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.request_lifecycle_gate import (
    RequestLifecycleCase,
    infer_lifecycle_decision,
    load_request_lifecycle_levels,
    run_request_lifecycle_promotion,
)


ROOT = Path(__file__).resolve().parents[2]


def test_request_lifecycle_levels_scale_to_hop_50() -> None:
    levels = load_request_lifecycle_levels(ROOT / "configs" / "request_lifecycle_gates.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert [level.max_hop_depth for level in levels] == [6, 15, 30, 50]


def test_request_lifecycle_promotion_passes() -> None:
    results = run_request_lifecycle_promotion(
        config_path=ROOT / "configs" / "request_lifecycle_gates.yaml"
    )

    assert [result.level for result in results] == ["easy", "medium", "hard", "extreme"]
    assert all(result.passed for result in results)


def test_request_lifecycle_modules_include_conflict_modules() -> None:
    data = load_yaml(ROOT / "configs" / "request_lifecycle_gates.yaml")

    assert "MEMORY" in data["lifecycle_modules"]
    assert "PATCH_PIPELINE" in data["lifecycle_modules"]
    assert data["max_supported_hop_depth"] == 50


def test_all_paths_invalid_stops() -> None:
    case = RequestLifecycleCase(
        id="unit",
        flow=["USER", "GATEWAY", "DECISION_GATE", "STOP"],
        conflict_type="all_paths_invalid",
        expected_decision="stop",
        hop_depth=50,
    )

    assert infer_lifecycle_decision(case) == "stop"

