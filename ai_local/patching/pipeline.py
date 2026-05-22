from ai_local.harness.patch_levels import PatchLevel
from ai_local.evaluator.service import route_evaluation
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
    max_retries_per_patch: int | None = None,
) -> PatchDecision:
    if not attempt.context_ready:
        return _retry_or_exhaust(
            attempt,
            PatchDecision("retrieve_more", "RETRIEVE_CONTEXT", ["context not ready"]),
            max_retries_per_patch,
        )
    pre_apply_trace_error = _validate_stage_order(attempt.completed_stages, PRE_APPLY_STAGES)
    if pre_apply_trace_error:
        return _retry_or_exhaust(
            attempt,
            PatchDecision("retry", "MODEL_PROPOSE_PATCH", [pre_apply_trace_error]),
            max_retries_per_patch,
        )
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
        return _retry_or_exhaust(
            attempt,
            PatchDecision("retry", "MODEL_PROPOSE_PATCH", policy.reasons),
            max_retries_per_patch,
        )
    if not attempt.semantic_review_passed:
        return _retry_or_exhaust(
            attempt,
            PatchDecision("retry", "MODEL_PROPOSE_PATCH", ["semantic review failed"]),
            max_retries_per_patch,
        )
    failures = [check for check in attempt.checks if not check.passed]
    if any(check.serious for check in failures):
        return PatchDecision("rollback", "ROLLBACK", ["serious check failed"])
    if failures:
        return _retry_or_exhaust(
            attempt,
            PatchDecision("retry", "MODEL_PROPOSE_PATCH", ["focused check failed"]),
            max_retries_per_patch,
        )
    missing_check_results = required_checks - {check.id for check in attempt.checks}
    if missing_check_results:
        return _retry_or_exhaust(
            attempt,
            PatchDecision(
                "retry",
                "RUN_FOCUSED_TESTS",
                [
                    f"required check result missing: {check_id}"
                    for check_id in sorted(missing_check_results)
                ],
            ),
            max_retries_per_patch,
        )
    unevidenced_checks = [
        check.id
        for check in attempt.checks
        if check.id in required_checks
        and (check.evidence_ref is None or check.evidence_ref.kind != "test")
    ]
    if unevidenced_checks:
        return _retry_or_exhaust(
            attempt,
            PatchDecision(
                "retry",
                "RUN_FOCUSED_TESTS",
                [
                    f"required check evidence missing: {check_id}"
                    for check_id in sorted(unevidenced_checks)
                ],
            ),
            max_retries_per_patch,
        )
    if not attempt.evaluator_passed:
        return _retry_or_exhaust(
            attempt,
            PatchDecision("retry", "PATCH_EVALUATOR", ["patch evaluator failed"]),
            max_retries_per_patch,
        )
    if (
        attempt.evaluator_evidence_ref is None
        or attempt.evaluator_evidence_ref.kind not in {"test", "manual"}
    ):
        return _retry_or_exhaust(
            attempt,
            PatchDecision(
                "retry",
                "PATCH_EVALUATOR",
                ["patch evaluator evidence missing"],
            ),
            max_retries_per_patch,
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
        return _retry_or_exhaust(
            attempt,
            PatchDecision("retry", next_stage, [post_apply_trace_error]),
            max_retries_per_patch,
        )
    evaluation_decision = _route_evaluation_result(attempt)
    if evaluation_decision:
        return _retry_or_exhaust(attempt, evaluation_decision, max_retries_per_patch)
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


def _retry_or_exhaust(
    attempt: PatchAttempt,
    decision: PatchDecision,
    max_retries_per_patch: int | None,
) -> PatchDecision:
    if decision.decision not in {"retry", "retrieve_more"}:
        return decision
    if max_retries_per_patch is None or attempt.retry_count < max_retries_per_patch:
        return decision
    reason = [*decision.reasons, "patch retry budget exhausted"]
    if "APPLY_PATCH" in attempt.completed_stages:
        return PatchDecision("rollback", "ROLLBACK", reason)
    return PatchDecision("ask_user", "ASK_USER", reason)


def _route_evaluation_result(attempt: PatchAttempt) -> PatchDecision | None:
    result = attempt.evaluation_result
    if result is None:
        return None
    route = route_evaluation(result)
    if route.decision == "accept":
        return None
    return PatchDecision(
        route.decision,
        route.next_state,
        [f"evaluation {route.decision}: {route.reason}"],
    )
