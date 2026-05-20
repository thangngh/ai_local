from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.evidence_rank_gate import (
    EvidenceRankCase,
    calculate_rank,
    load_evidence_rank_levels,
    rank_band,
    run_evidence_rank_promotion,
)


ROOT = Path(__file__).resolve().parents[2]


def test_evidence_rank_levels_scale_to_hop_50() -> None:
    levels = load_evidence_rank_levels(ROOT / "configs" / "evidence_rank_gates.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert [level.max_hop_depth for level in levels] == [4, 10, 25, 50]


def test_evidence_rank_promotion_passes_all_levels() -> None:
    results = run_evidence_rank_promotion(
        config_path=ROOT / "configs" / "evidence_rank_gates.yaml"
    )

    assert [result.level for result in results] == ["easy", "medium", "hard", "extreme"]
    assert all(result.passed for result in results)


def test_evidence_rank_config_has_hard_reject_noise() -> None:
    data = load_yaml(ROOT / "configs" / "evidence_rank_gates.yaml")

    assert "prompt_injection" in data["hard_reject_noise"]
    assert data["max_supported_hop_depth"] == 50


def test_rank_formula_and_band() -> None:
    case = EvidenceRankCase(
        id="unit",
        source_authority=30,
        evidence_strength=25,
        freshness=15,
        project_relevance=15,
        confirmation_weight=15,
        conflict_penalty=0,
        staleness_penalty=0,
        noise_type="none",
        expected_band="canonical",
        hop_depth=1,
    )

    assert calculate_rank(case) == 100
    assert rank_band(case) == "canonical"

