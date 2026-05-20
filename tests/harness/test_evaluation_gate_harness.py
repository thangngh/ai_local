from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.evaluation_gate import (
    EvaluationCase,
    evaluation_score,
    infer_evaluation_band,
    load_evaluation_levels,
    run_evaluation_promotion,
)


ROOT = Path(__file__).resolve().parents[2]


def test_evaluation_levels_scale_to_hop_50() -> None:
    levels = load_evaluation_levels(ROOT / "configs" / "evaluation_gates.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert [level.max_hop_depth for level in levels] == [3, 8, 20, 50]


def test_evaluation_promotion_passes_all_levels() -> None:
    results = run_evaluation_promotion(config_path=ROOT / "configs" / "evaluation_gates.yaml")

    assert [result.level for result in results] == ["easy", "medium", "hard", "extreme"]
    assert all(result.passed for result in results)


def test_evaluation_formula_config_contains_expected_weights() -> None:
    data = load_yaml(ROOT / "configs" / "evaluation_gates.yaml")

    assert data["score_formula"]["correctness"] == 0.25
    assert data["score_formula"]["risk_penalty"] == -0.10
    assert data["max_supported_hop_depth"] == 50


def test_evaluation_score_accepts_clean_case() -> None:
    case = EvaluationCase(
        id="unit",
        correctness=1.0,
        completeness=1.0,
        evidence_quality=1.0,
        requirement_match=1.0,
        test_status=1.0,
        ambiguity=0.0,
        risk=0.0,
        expected_band="accept",
        hop_depth=1,
        noise_type=None,
    )

    assert evaluation_score(case) == 0.9
    assert infer_evaluation_band(case) == "accept"

