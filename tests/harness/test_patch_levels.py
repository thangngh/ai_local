from pathlib import Path

from ai_local.harness.patch_levels import load_patch_levels, validate_patch_levels
from ai_local.harness.small_patch_harness import load_small_patch_levels
from ai_local.harness.patch_pipeline_harness import load_patch_pipeline_levels


ROOT = Path(__file__).resolve().parents[2]


def test_patch_levels_are_ordered_and_valid() -> None:
    levels = load_patch_levels(ROOT / "configs" / "patch_levels.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert validate_patch_levels(levels) == []


def test_patch_levels_match_small_patch_hop_depths() -> None:
    patch_levels = load_patch_levels(ROOT / "configs" / "patch_levels.yaml")
    small_levels = load_small_patch_levels(ROOT / "configs" / "small_patch_harness.yaml")

    assert [level.max_hop_depth for level in patch_levels] == [
        level.max_hop_depth for level in small_levels
    ]


def test_patch_levels_match_pipeline_hop_depths_except_easy_name_limit() -> None:
    patch_levels = load_patch_levels(ROOT / "configs" / "patch_levels.yaml")
    pipeline_levels = load_patch_pipeline_levels(ROOT / "configs" / "patch_pipeline_harness.yaml")

    assert [level.max_hop_depth for level in patch_levels] == [5, 12, 25, 50]
    assert [level.max_hop_depth for level in pipeline_levels] == [6, 12, 25, 50]

