from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.confirmation_gate import (
    ConfirmationCase,
    infer_confirmation_decision,
    load_confirmation_levels,
    parse_confirmation_flow,
    run_confirmation_promotion,
)


ROOT = Path(__file__).resolve().parents[2]


def test_confirmation_levels_scale_to_hop_50() -> None:
    levels = load_confirmation_levels(ROOT / "configs" / "confirmation_gates.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert [level.max_hop_depth for level in levels] == [3, 8, 15, 50]


def test_confirmation_promotion_passes_all_levels() -> None:
    results = run_confirmation_promotion(config_path=ROOT / "configs" / "confirmation_gates.yaml")

    assert [result.level for result in results] == ["easy", "medium", "hard", "extreme"]
    assert all(result.passed for result in results)


def test_confirmation_policy_has_required_question_parts() -> None:
    data = load_yaml(ROOT / "configs" / "confirmation_gates.yaml")

    assert data["confirmation_policy"]["save_as_knowledge"]["confirmed_policy"] == (
        "K6_DECISION_POLICY"
    )
    assert "recommendation" in data["confirmation_policy"]["required_question_parts"]
    assert data["max_supported_hop_depth"] == 50


def test_parse_confirmation_flow() -> None:
    assert parse_confirmation_flow("A -> B -> C") == ["A", "B", "C"]


def test_fake_approval_laundering_stops() -> None:
    case = ConfirmationCase(
        id="unit",
        flow=["DECISION_GATE", "EXPLICIT_APPROVAL"],
        trigger="dangerous_action",
        noise_type="fake_approval_laundering",
        expected_decision="stop",
        hop_depth=50,
    )

    assert infer_confirmation_decision(case) == "stop"

