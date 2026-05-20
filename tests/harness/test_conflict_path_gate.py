from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.conflict_path_gate import (
    ConflictPath,
    ConflictPathCase,
    infer_conflict_decision,
    load_conflict_path_levels,
    run_conflict_path_promotion,
)


ROOT = Path(__file__).resolve().parents[2]


def test_conflict_path_levels_scale_to_hop_50() -> None:
    levels = load_conflict_path_levels(ROOT / "configs" / "conflict_path_gates.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert [level.max_hop_depth for level in levels] == [5, 12, 25, 50]


def test_conflict_path_promotion_passes_all_levels() -> None:
    results = run_conflict_path_promotion(
        config_path=ROOT / "configs" / "conflict_path_gates.yaml"
    )

    assert [result.level for result in results] == ["easy", "medium", "hard", "extreme"]
    assert all(result.passed for result in results)


def test_conflict_path_precedence_defined() -> None:
    data = load_yaml(ROOT / "configs" / "conflict_path_gates.yaml")

    assert data["path_policy"]["precedence"][0] == "current_user_instruction"
    assert data["max_supported_hop_depth"] == 50


def test_no_path_stops_for_unsafe_routes() -> None:
    case = ConflictPathCase(
        id="unit",
        conflict_type="all_routes_unsafe",
        paths=[ConflictPath("a", False), ConflictPath("b", False)],
        forced_choice_required=False,
        expected_decision="stop",
        expected_path=None,
        hop_depth=50,
    )

    assert infer_conflict_decision(case) == ("stop", None)

