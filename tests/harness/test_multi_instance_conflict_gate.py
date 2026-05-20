from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.multi_instance_conflict_gate import (
    ConflictInstance,
    MultiInstanceConflictCase,
    infer_multi_instance_decision,
    load_multi_instance_conflict_levels,
    run_multi_instance_conflict_promotion,
)


ROOT = Path(__file__).resolve().parents[2]


def test_multi_instance_conflict_levels_scale_to_hop_50() -> None:
    levels = load_multi_instance_conflict_levels(
        ROOT / "configs" / "multi_instance_conflict_gates.yaml"
    )

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert [level.max_hop_depth for level in levels] == [8, 15, 30, 50]


def test_multi_instance_conflict_promotion_passes() -> None:
    results = run_multi_instance_conflict_promotion(
        config_path=ROOT / "configs" / "multi_instance_conflict_gates.yaml"
    )

    assert [result.level for result in results] == ["easy", "medium", "hard", "extreme"]
    assert all(result.passed for result in results)


def test_multi_instance_policy_has_no_path_decisions() -> None:
    data = load_yaml(ROOT / "configs" / "multi_instance_conflict_gates.yaml")

    assert "defer_until_evidence" in data["decision_policy"]
    assert data["max_supported_hop_depth"] == 50


def test_unresolved_equivalence_asks_user() -> None:
    case = MultiInstanceConflictCase(
        id="unit",
        modules=["memory", "retrieval"],
        instances=[
            ConflictInstance("a", 80, 0.5, "mixed"),
            ConflictInstance("b", 80, 0.5, "mixed"),
        ],
        conflict_type="unresolved_equivalence_class",
        expected_decision="ask_user",
        hop_depth=50,
    )

    assert infer_multi_instance_decision(case) == "ask_user"

