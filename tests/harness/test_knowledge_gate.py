from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.knowledge_gate import (
    KnowledgeCase,
    infer_knowledge_decision,
    load_knowledge_levels,
    parse_knowledge_flow,
    run_knowledge_promotion,
)


ROOT = Path(__file__).resolve().parents[2]


def test_knowledge_levels_scale_to_hop_50() -> None:
    levels = load_knowledge_levels(ROOT / "configs" / "knowledge_gates.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert [level.max_hop_depth for level in levels] == [4, 10, 20, 50]


def test_knowledge_promotion_passes_all_levels() -> None:
    results = run_knowledge_promotion(config_path=ROOT / "configs" / "knowledge_gates.yaml")

    assert [result.level for result in results] == ["easy", "medium", "hard", "extreme"]
    assert all(result.passed for result in results)


def test_knowledge_priority_order_matches_policy() -> None:
    data = load_yaml(ROOT / "configs" / "knowledge_gates.yaml")

    assert data["priority_order"] == [
        "K6_DECISION_POLICY",
        "K5_GROUND_TRUTH",
        "K2_PROJECT",
        "K3_CURRENT",
        "K4_ADVANCED",
        "K1_BASIC",
        "K0_UNKNOWN",
    ]
    assert data["max_supported_hop_depth"] == 50


def test_parse_knowledge_flow() -> None:
    assert parse_knowledge_flow("CLAIM -> RANKER -> KNOWLEDGE_GATE") == [
        "CLAIM",
        "RANKER",
        "KNOWLEDGE_GATE",
    ]


def test_prompt_injected_knowledge_quarantines() -> None:
    case = KnowledgeCase(
        id="unit",
        flow=["CLAIM", "KNOWLEDGE_GATE"],
        knowledge_level="K2_PROJECT",
        rank=90,
        confidence=0.9,
        evidence_strength=0.9,
        conflict_score=0.0,
        noise_type="prompt_injection",
        expected_decision="quarantine",
        hop_depth=1,
    )

    assert infer_knowledge_decision(case) == "quarantine"

