from pathlib import Path

from ai_local.harness.patch_levels import load_patch_levels
from ai_local.harness.small_patch_harness import load_small_patch_levels
from ai_local.patching.models import (
    PatchAttempt,
    PatchChangeSummary,
    PatchCheckResult,
    PatchHarnessSpec,
)
from ai_local.patching.pipeline import decide_patch_attempt


ROOT = Path(__file__).resolve().parents[1]


def _medium_attempt(**overrides: object) -> PatchAttempt:
    harness_level = load_small_patch_levels(ROOT / "configs" / "small_patch_harness.yaml")[1]
    attempt = PatchAttempt(
        harness=PatchHarnessSpec(
            requirement_id="F-HAR-002",
            objective="Execute patch pipeline",
            level="medium",
            allowed_files=["ai_local/patching/pipeline.py", "tests/test_patch_pipeline_runtime.py"],
            evidence=set(harness_level.required_evidence),
            checks=set(harness_level.required_checks),
        ),
        summary=PatchChangeSummary(
            files_changed=["ai_local/patching/pipeline.py"],
            changed_lines=60,
            functions_changed=1,
        ),
        context_ready=True,
        semantic_review_passed=True,
        checks=[PatchCheckResult(id="focused", passed=True, evidence_ref="pytest")],
    )
    return PatchAttempt(**{**attempt.__dict__, **overrides})


def _decide(attempt: PatchAttempt) -> str:
    level = load_patch_levels(ROOT / "configs" / "patch_levels.yaml")[1]
    harness_level = load_small_patch_levels(ROOT / "configs" / "small_patch_harness.yaml")[1]
    return decide_patch_attempt(
        attempt,
        level,
        required_evidence=set(harness_level.required_evidence),
        required_checks=set(harness_level.required_checks),
    ).decision


def test_patch_pipeline_retrieves_more_and_accepts_ready_patch() -> None:
    assert _decide(_medium_attempt(context_ready=False)) == "retrieve_more"
    assert _decide(_medium_attempt()) == "accept"


def test_patch_pipeline_retries_or_rolls_back_failed_checks() -> None:
    retry = _medium_attempt(checks=[PatchCheckResult(id="focused", passed=False)])
    rollback = _medium_attempt(checks=[PatchCheckResult(id="focused", passed=False, serious=True)])

    assert _decide(retry) == "retry"
    assert _decide(rollback) == "rollback"


def test_patch_pipeline_continues_to_next_patch() -> None:
    assert _decide(_medium_attempt(more_patch_required=True)) == "next_patch"
