from ai_local.harness.patch_levels import PatchLevel
from ai_local.patching.models import PatchAttempt, PatchDecision
from ai_local.patching.policy import validate_patch_harness


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
POST_APPLY_STAGES = [
    "RUN_FOCUSED_TESTS",
    "TEST_GATE",
    "PATCH_EVALUATOR",
]


def decide_patch_attempt(
    attempt: PatchAttempt,
    level: PatchLevel,
    *,
    required_evidence: set[str],
    required_checks: set[str],
) -> PatchDecision:
    if not attempt.context_ready:
        return PatchDecision("retrieve_more", "RETRIEVE_CONTEXT", ["context not ready"])
    pre_apply_trace_error = _validate_stage_order(attempt.completed_stages, PRE_APPLY_STAGES)
    if pre_apply_trace_error:
        return PatchDecision("retry", "MODEL_PROPOSE_PATCH", [pre_apply_trace_error])
    policy = validate_patch_harness(
        attempt.harness,
        attempt.summary,
        level,
        required_evidence=required_evidence,
        required_checks=required_checks,
    )
    if policy.decision == "split":
        return PatchDecision("split", "PATCH_OBJECTIVE", policy.reasons)
    if policy.decision == "ask_user":
        return PatchDecision("ask_user", "ASK_USER", policy.reasons)
    if not policy.passed:
        return PatchDecision("retry", "MODEL_PROPOSE_PATCH", policy.reasons)
    if not attempt.semantic_review_passed:
        return PatchDecision("retry", "MODEL_PROPOSE_PATCH", ["semantic review failed"])
    failures = [check for check in attempt.checks if not check.passed]
    if any(check.serious for check in failures):
        return PatchDecision("rollback", "ROLLBACK", ["serious check failed"])
    if failures:
        return PatchDecision("retry", "MODEL_PROPOSE_PATCH", ["focused check failed"])
    missing_check_results = required_checks - {check.id for check in attempt.checks}
    if missing_check_results:
        return PatchDecision(
            "retry",
            "RUN_FOCUSED_TESTS",
            [f"required check result missing: {check_id}" for check_id in sorted(missing_check_results)],
        )
    unevidenced_checks = [
        check.id
        for check in attempt.checks
        if check.id in required_checks
        and (check.evidence_ref is None or check.evidence_ref.kind != "test")
    ]
    if unevidenced_checks:
        return PatchDecision(
            "retry",
            "RUN_FOCUSED_TESTS",
            [f"required check evidence missing: {check_id}" for check_id in sorted(unevidenced_checks)],
        )
    if not attempt.evaluator_passed:
        return PatchDecision("retry", "PATCH_EVALUATOR", ["patch evaluator failed"])
    if (
        attempt.evaluator_evidence_ref is None
        or attempt.evaluator_evidence_ref.kind not in {"test", "manual"}
    ):
        return PatchDecision(
            "retry",
            "PATCH_EVALUATOR",
            ["patch evaluator evidence missing"],
        )
    post_apply_trace_error = _validate_stage_order(
        attempt.completed_stages,
        [*PRE_APPLY_STAGES, *POST_APPLY_STAGES],
    )
    if post_apply_trace_error:
        next_stage = (
            "RUN_FOCUSED_TESTS"
            if "RUN_FOCUSED_TESTS" in post_apply_trace_error
            or "TEST_GATE" in post_apply_trace_error
            else "PATCH_EVALUATOR"
        )
        return PatchDecision("retry", next_stage, [post_apply_trace_error])
    if attempt.more_patch_required:
        return PatchDecision("next_patch", "NEXT_PATCH", ["more patch work remains"])
    return PatchDecision("accept", "DECISION_GATE", ["patch evidence and checks passed"])


def _validate_stage_order(completed_stages: list[str], required_stages: list[str]) -> str | None:
    position = -1
    for stage in required_stages:
        try:
            position = completed_stages.index(stage, position + 1)
        except ValueError:
            return f"required stage missing or out of order: {stage}"
    return None
