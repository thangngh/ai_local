from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.patch_pipeline_harness import (
    infer_patch_pipeline_decision,
    load_patch_pipeline_levels,
    parse_pipeline_flow,
    run_patch_pipeline_promotion,
    PatchPipelineCase,
)


ROOT = Path(__file__).resolve().parents[2]


def test_patch_pipeline_levels_scale_to_hop_50() -> None:
    levels = load_patch_pipeline_levels(ROOT / "configs" / "patch_pipeline_harness.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert [level.max_hop_depth for level in levels] == [6, 12, 25, 50]


def test_patch_pipeline_promotion_passes_all_levels() -> None:
    results = run_patch_pipeline_promotion(
        config_path=ROOT / "configs" / "patch_pipeline_harness.yaml"
    )

    assert [result.level for result in results] == ["easy", "medium", "hard", "extreme"]
    assert all(result.passed for result in results)


def test_patch_pipeline_required_stages_include_apply_and_evaluator() -> None:
    data = load_yaml(ROOT / "configs" / "patch_pipeline_harness.yaml")
    stages = data["patch_pipeline"]["required_stages"]

    assert "APPLY_PATCH" in stages
    assert "PATCH_EVALUATOR" in stages
    assert data["patch_pipeline"]["max_supported_hop_depth"] == 50


def test_parse_pipeline_flow() -> None:
    assert parse_pipeline_flow("A -> B -> C") == ["A", "B", "C"]


def test_deep_prompt_laundering_rolls_back() -> None:
    case = PatchPipelineCase(
        id="unit",
        flow=["PATCH_OBJECTIVE", "DECISION_GATE"],
        expected_decision="rollback",
        noise_type="deep_prompt_laundering",
        hop_depth=50,
    )

    assert infer_patch_pipeline_decision(case) == "rollback"

