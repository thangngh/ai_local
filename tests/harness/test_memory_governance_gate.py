from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.memory_governance_gate import (
    MemoryGovernanceCase,
    infer_memory_governance_decision,
    load_memory_governance_levels,
    run_memory_governance_promotion,
)


ROOT = Path(__file__).resolve().parents[2]


def test_memory_governance_levels_scale_to_hop_50() -> None:
    levels = load_memory_governance_levels(ROOT / "configs" / "memory_governance_gates.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert [level.max_hop_depth for level in levels] == [6, 15, 30, 50]


def test_memory_governance_promotion_passes() -> None:
    results = run_memory_governance_promotion(
        config_path=ROOT / "configs" / "memory_governance_gates.yaml"
    )

    assert all(result.passed for result in results)


def test_memory_governance_gate_tracks_scores() -> None:
    data = load_yaml(ROOT / "configs" / "memory_governance_gates.yaml")

    assert "WRITE_SCORE" in data["memory_governance_modules"]
    assert "RETRIEVAL_SCORE" in data["memory_governance_modules"]
    assert "DEMOTION_GATE" in data["memory_governance_modules"]


def test_secret_candidate_is_rejected() -> None:
    case = MemoryGovernanceCase(
        id="unit",
        flow=["MEMORY_CANDIDATE", "RISK_SCORE", "WRITE_GATE"],
        scenario="secret_candidate",
        expected_decision="reject_memory",
        hop_depth=6,
    )

    assert infer_memory_governance_decision(case) == "reject_memory"
