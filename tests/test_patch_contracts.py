from pathlib import Path

from ai_local.harness.patch_levels import load_patch_levels
from ai_local.harness.small_patch_harness import load_small_patch_levels
from ai_local.patching.models import (
    PatchChangeSummary,
    PatchEvidenceRef,
    PatchFileChange,
    PatchHarnessSpec,
)
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
        evidence_refs=[
            PatchEvidenceRef("context", "docs/requirements.md:F-HAR-001"),
            PatchEvidenceRef("test", "pytest:tests/test_patch_contracts.py"),
        ],
        checks=set(medium_harness.required_checks),
    )
    summary = PatchChangeSummary.from_diff(
        [
            PatchFileChange(
                path="ai_local/patching/policy.py",
                added_lines=35,
                removed_lines=5,
                functions_changed=1,
                change_types={"feature_slice"},
            ),
            PatchFileChange(
                path="tests/test_patch_contracts.py",
                added_lines=40,
                removed_lines=0,
                functions_changed=1,
                change_types={"tests"},
            ),
        ],
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
        evidence_refs=[PatchEvidenceRef("context", "configs/small_patch_harness.yaml:easy")],
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
            evidence_refs=[PatchEvidenceRef("context", "configs/patch_levels.yaml:hard")],
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


def test_patch_harness_rejects_missing_evidence_ref_and_forbidden_change_type() -> None:
    medium = load_patch_levels(ROOT / "configs" / "patch_levels.yaml")[1]
    result = validate_patch_harness(
        PatchHarnessSpec(
            requirement_id="F-HAR-001",
            objective="Dependency patch",
            level="medium",
            allowed_files=["pyproject.toml"],
            evidence={"requirement_id"},
            checks={"test.harness"},
        ),
        PatchChangeSummary.from_diff(
            [
                PatchFileChange(
                    path="pyproject.toml",
                    added_lines=1,
                    removed_lines=0,
                    change_types={"dependency_change"},
                )
            ],
        ),
        medium,
        required_evidence={"requirement_id"},
        required_checks={"test.harness"},
    )

    assert not result.passed
    assert "evidence refs missing" in result.reasons
    assert "forbidden change type" in result.reasons


def test_hard_patch_harness_requires_diff_and_focused_test_evidence_refs() -> None:
    hard = load_patch_levels(ROOT / "configs" / "patch_levels.yaml")[2]
    hard_harness = load_small_patch_levels(ROOT / "configs" / "small_patch_harness.yaml")[2]

    result = validate_patch_harness(
        PatchHarnessSpec(
            requirement_id="F-HAR-002",
            objective="Patch evidence chain",
            level="hard",
            allowed_files=["ai_local/patching/pipeline.py"],
            evidence=set(hard_harness.required_evidence),
            evidence_refs=[PatchEvidenceRef("context", "retrieval:patch-pipeline")],
            checks=set(hard_harness.required_checks),
            rollback_plan="restore previous diff",
        ),
        PatchChangeSummary.from_diff(
            [
                PatchFileChange(
                    path="ai_local/patching/pipeline.py",
                    added_lines=10,
                    removed_lines=2,
                    change_types={"patch_pipeline"},
                )
            ]
        ),
        hard,
        required_evidence=set(hard_harness.required_evidence),
        required_checks=set(hard_harness.required_checks),
    )

    assert "diff evidence ref missing" in result.reasons
    assert "focused harness evidence ref missing" in result.reasons
