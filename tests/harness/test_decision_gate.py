from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.decision_gate import (
    DecisionCase,
    infer_decision,
    load_decision_levels,
    run_decision_promotion,
)


ROOT = Path(__file__).resolve().parents[2]


def test_decision_levels_cover_basic_to_deep_hop() -> None:
    levels = load_decision_levels(ROOT / "configs" / "decision_gates.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert [level.max_hop_depth for level in levels] == [2, 5, 10, 20]


def test_decision_promotion_passes_all_levels() -> None:
    results = run_decision_promotion(config_path=ROOT / "configs" / "decision_gates.yaml")

    assert [result.level for result in results] == ["easy", "medium", "hard", "extreme"]
    assert all(result.passed for result in results)


def test_decision_policy_supports_security_outcomes() -> None:
    data = load_yaml(ROOT / "configs" / "decision_gates.yaml")

    assert "verify" in data["decision_policy"]
    assert "quarantine" in data["decision_policy"]
    assert "stop" in data["decision_policy"]


def test_infer_decision_stops_on_deep_policy_shadowing() -> None:
    case = DecisionCase(
        id="unit",
        flow="task -> decision",
        score=0.99,
        risk=0.10,
        ambiguity=0.10,
        retries=0,
        expected_decision="stop",
        hop_depth=20,
        security_signal="deep_policy_shadowing",
    )

    assert infer_decision(case) == "stop"

