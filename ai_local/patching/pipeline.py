from ai_local.harness.patch_levels import PatchLevel
from ai_local.patching.models import PatchAttempt, PatchDecision
from ai_local.patching.policy import validate_patch_harness


def decide_patch_attempt(
    attempt: PatchAttempt,
    level: PatchLevel,
    *,
    required_evidence: set[str],
    required_checks: set[str],
) -> PatchDecision:
    if not attempt.context_ready:
        return PatchDecision("retrieve_more", "RETRIEVE_CONTEXT", ["context not ready"])
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
    if attempt.more_patch_required:
        return PatchDecision("next_patch", "NEXT_PATCH", ["more patch work remains"])
    return PatchDecision("accept", "DECISION_GATE", ["patch evidence and checks passed"])
