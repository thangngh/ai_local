from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.operational_safety_gate import (
    OperationalSafetyCase,
    infer_operational_decision,
    load_operational_safety_levels,
    run_operational_safety_promotion,
)


ROOT = Path(__file__).resolve().parents[2]


def test_operational_safety_levels_scale_to_hop_50() -> None:
    levels = load_operational_safety_levels(ROOT / "configs" / "operational_safety_gates.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert [level.max_hop_depth for level in levels] == [6, 15, 30, 50]


def test_operational_safety_promotion_passes() -> None:
    results = run_operational_safety_promotion(
        config_path=ROOT / "configs" / "operational_safety_gates.yaml"
    )

    assert all(result.passed for result in results)


def test_operational_safety_gate_tracks_subpage_modules() -> None:
    data = load_yaml(ROOT / "configs" / "operational_safety_gates.yaml")

    assert "JOB_QUEUE" in data["operational_modules"]
    assert "OUTBOX" in data["operational_modules"]
    assert "PROMPT_FIREWALL" in data["operational_modules"]


def test_retry_budget_exhaustion_dead_letters_job() -> None:
    case = OperationalSafetyCase(
        id="unit",
        flow=["JOB_QUEUE", "WORKER", "RETRY_POLICY", "DEAD_LETTER"],
        scenario="retry_budget_exhausted",
        expected_decision="dead_letter_job",
        hop_depth=50,
    )

    assert infer_operational_decision(case) == "dead_letter_job"
