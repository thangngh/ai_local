from pathlib import Path

from ai_local.harness.patch_levels import load_patch_levels
from ai_local.harness.small_patch_harness import load_small_patch_levels
from ai_local.patching.models import PatchChangeSummary, PatchHarnessSpec
from ai_local.patching.policy import validate_patch_harness


ROOT = Path(__file__).resolve().parents[1]


def test_patch_harness_accepts_scoped_medium_patch() -> None:
    medium = load_patch_levels(ROOT / "configs" / "patch_levels.yaml")[1]
    medium_harness = load_small_patch_levels(ROOT / "configs" / "small_patch_harness.yaml")[1]
    spec = PatchHarnessSpec(
        requirement_id="F-HAR-001",
        objective="Add patch contract",
        level="medium",
        allowed_files=["ai_local/patching/policy.py", "tests/test_patch_contracts.py"],
        evidence=set(medium_harness.required_evidence),
        checks=set(medium_harness.required_checks),
    )
    summary = PatchChangeSummary(
        files_changed=["ai_local/patching/policy.py", "tests/test_patch_contracts.py"],
        changed_lines=80,
        functions_changed=2,
    )

    result = validate_patch_harness(
        spec,
        summary,
        medium,
        required_evidence=set(medium_harness.required_evidence),
        required_checks=set(medium_harness.required_checks),
    )

    assert result.passed
    assert result.decision == "continue"


def test_patch_harness_splits_oversized_patch_and_asks_on_risk() -> None:
    easy, hard = load_patch_levels(ROOT / "configs" / "patch_levels.yaml")[0::2]
    spec = PatchHarnessSpec(
        requirement_id="F-HAR-001",
        objective="Patch policy",
        level="easy",
        allowed_files=["ai_local/patching/policy.py"],
        evidence={"requirement_id"},
        checks={"test.harness"},
    )

    split = validate_patch_harness(
        spec,
        PatchChangeSummary(
            files_changed=["ai_local/patching/policy.py"],
            changed_lines=41,
            functions_changed=1,
        ),
        easy,
        required_evidence={"requirement_id"},
        required_checks={"test.harness"},
    )
    ask = validate_patch_harness(
        PatchHarnessSpec(
            requirement_id="F-HAR-002",
            objective="High risk patch",
            level="hard",
            allowed_files=["ai_local/patching/pipeline.py"],
            evidence={"requirement_id"},
            checks={"test.harness"},
            rollback_plan="restore before apply",
        ),
        PatchChangeSummary(
            files_changed=["ai_local/patching/pipeline.py"],
            changed_lines=20,
            functions_changed=1,
            risk=0.9,
        ),
        hard,
        required_evidence={"requirement_id"},
        required_checks={"test.harness"},
    )

    assert split.decision == "split"
    assert ask.decision == "ask_user"
