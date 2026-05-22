from pathlib import Path

from ai_local.harness.patch_levels import load_patch_levels
from ai_local.harness.small_patch_harness import load_small_patch_levels
from ai_local.patching.models import (
    PatchAttempt,
    PatchChangeSummary,
    PatchCheckResult,
    PatchEvidenceRef,
    PatchHarnessSpec,
)
from ai_local.patching.pipeline import decide_patch_attempt


ROOT = Path(__file__).resolve().parents[1]
PRE_APPLY_STAGES = [
    "PATCH_OBJECTIVE",
    "CREATE_PATCH_HARNESS",
    "RETRIEVE_CONTEXT",
    "CONTEXT_GATE",
    "MODEL_PROPOSE_PATCH",
    "DIFF_STATIC_CHECK",
    "SCOPE_GATE",
    "PATCH_SIZE_GATE",
    "RISK_GATE",
    "SEMANTIC_PATCH_REVIEW",
    "APPLY_PATCH",
]
POST_APPLY_STAGES = ["RUN_FOCUSED_TESTS", "TEST_GATE", "PATCH_EVALUATOR"]


def _medium_attempt(**overrides: object) -> PatchAttempt:
    harness_level = load_small_patch_levels(ROOT / "configs" / "small_patch_harness.yaml")[1]
    attempt = PatchAttempt(
        harness=PatchHarnessSpec(
            requirement_id="F-HAR-002",
            objective="Execute patch pipeline",
            level="medium",
            allowed_files=["ai_local/patching/pipeline.py", "tests/test_patch_pipeline_runtime.py"],
            evidence=set(harness_level.required_evidence),
            evidence_refs=[
                PatchEvidenceRef("context", "docs/patch-pipeline-harness.md:F-HAR-002"),
                PatchEvidenceRef("test", "pytest:tests/test_patch_pipeline_runtime.py"),
            ],
            checks=set(harness_level.required_checks),
        ),
        summary=PatchChangeSummary(
            files_changed=["ai_local/patching/pipeline.py"],
            changed_lines=60,
            functions_changed=1,
        ),
        context_ready=True,
        semantic_review_passed=True,
        checks=[
            PatchCheckResult(
                id="test.harness",
                passed=True,
                evidence_ref=PatchEvidenceRef("test", "pytest:tests/harness"),
            ),
            PatchCheckResult(
                id="test.pytest",
                passed=True,
                evidence_ref=PatchEvidenceRef("test", "pytest:tests/test_patch_pipeline_runtime.py"),
            ),
        ],
        completed_stages=[*PRE_APPLY_STAGES, *POST_APPLY_STAGES],
        evaluator_evidence_ref=PatchEvidenceRef("test", "patch-evaluator:medium"),
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


def test_patch_pipeline_retries_missing_required_check_evidence() -> None:
    missing_result = _medium_attempt(checks=[])
    missing_evidence = _medium_attempt(
        checks=[
            PatchCheckResult(id="test.harness", passed=True),
            PatchCheckResult(
                id="test.pytest",
                passed=True,
                evidence_ref=PatchEvidenceRef("diff", "git diff -- tests"),
            ),
        ]
    )

    assert _decide(missing_result) == "retry"
    assert _decide(missing_evidence) == "retry"


def test_patch_pipeline_retries_missing_or_misordered_pre_apply_stage() -> None:
    missing_static_diff = _medium_attempt(
        completed_stages=[stage for stage in PRE_APPLY_STAGES if stage != "DIFF_STATIC_CHECK"]
    )
    late_scope_gate = _medium_attempt(
        completed_stages=[
            stage for stage in PRE_APPLY_STAGES if stage not in {"SCOPE_GATE", "APPLY_PATCH"}
        ]
        + ["APPLY_PATCH", "SCOPE_GATE"]
    )

    assert _decide(missing_static_diff) == "retry"
    assert _decide(late_scope_gate) == "retry"


def test_patch_pipeline_retries_failed_or_unevidenced_evaluator() -> None:
    failed = _medium_attempt(evaluator_passed=False)
    missing_evidence = _medium_attempt(evaluator_evidence_ref=None)
    wrong_evidence = _medium_attempt(
        evaluator_evidence_ref=PatchEvidenceRef("diff", "git diff --stat")
    )

    assert _decide(failed) == "retry"
    assert _decide(missing_evidence) == "retry"
    assert _decide(wrong_evidence) == "retry"


def test_patch_pipeline_retries_missing_or_misordered_post_apply_stage() -> None:
    missing_test_gate = _medium_attempt(
        completed_stages=[*PRE_APPLY_STAGES, "RUN_FOCUSED_TESTS", "PATCH_EVALUATOR"]
    )
    late_test_gate = _medium_attempt(
        completed_stages=[*PRE_APPLY_STAGES, "RUN_FOCUSED_TESTS", "PATCH_EVALUATOR", "TEST_GATE"]
    )
    missing_evaluator_stage = _medium_attempt(
        completed_stages=[*PRE_APPLY_STAGES, "RUN_FOCUSED_TESTS", "TEST_GATE"]
    )

    assert _decide(missing_test_gate) == "retry"
    assert _decide(late_test_gate) == "retry"
    assert _decide(missing_evaluator_stage) == "retry"


def test_patch_pipeline_continues_to_next_patch() -> None:
    assert _decide(_medium_attempt(more_patch_required=True)) == "next_patch"
