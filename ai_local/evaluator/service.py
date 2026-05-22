from ai_local.audit.store import InMemoryAuditStore, make_audit_event
from ai_local.confirmation.models import ConfirmationResolution
from ai_local.evaluator.models import (
    EvaluationDecision,
    EvaluationEvidence,
    ObservationEvaluationInput,
    EvaluationResult,
    EvaluationRoute,
    EvaluationScore,
    SecuritySignal,
)
from ai_local.retrieval.models import ContextPackage


def decide(score: EvaluationScore, retry_count: int) -> str:
    return evaluate(score, retry_count=retry_count).decision


def evaluate(
    score: EvaluationScore,
    *,
    retry_count: int,
    security_signal: SecuritySignal | None = None,
    evidence: EvaluationEvidence | None = None,
) -> EvaluationResult:
    if security_signal == "deep_policy_shadowing" or score.risk >= 0.85:
        return _result(score, retry_count, "stop", "risk ceiling reached", security_signal, evidence)
    if security_signal == "tool_policy_override":
        return _result(score, retry_count, "quarantine", "tool policy override", security_signal, evidence)
    if security_signal == "memory_conflict":
        return _result(score, retry_count, "verify", "memory evidence conflicts", security_signal, evidence)
    if score.ambiguity >= 0.60:
        return _result(
            score,
            retry_count,
            "ask_user",
            "ambiguity requires confirmation",
            security_signal,
            evidence,
        )
    if security_signal == "laundered_evidence":
        return _result(
            score,
            retry_count,
            "ask_user",
            "evidence authority is unclear",
            security_signal,
            evidence,
        )
    if score.evidence_quality <= 0.40:
        return _result(
            score,
            retry_count,
            "verify",
            "evidence quality below floor",
            security_signal,
            evidence,
        )
    if score.requirement_match <= 0.40:
        return _retry_or_ask(
            score,
            retry_count,
            "requirement match below floor",
            security_signal,
            evidence,
        )
    if score.final_score >= 0.80 and score.risk < 0.50 and score.test_status >= 0.50:
        return _result(
            score,
            retry_count,
            "accept",
            "score and risk thresholds passed",
            security_signal,
            evidence,
        )
    if score.final_score >= 0.60:
        return _retry_or_ask(
            score,
            retry_count,
            "score needs another patch attempt",
            security_signal,
            evidence,
        )
    return _result(
        score,
        retry_count,
        "ask_user",
        "score cannot promote automatically",
        security_signal,
        evidence,
    )


def _retry_or_ask(
    score: EvaluationScore,
    retry_count: int,
    reason: str,
    security_signal: SecuritySignal | None,
    evidence: EvaluationEvidence | None,
) -> EvaluationResult:
    if retry_count < 2:
        return _result(score, retry_count, "retry", reason, security_signal, evidence)
    return _result(
        score,
        retry_count,
        "ask_user",
        f"{reason}; retry budget exhausted",
        security_signal,
        evidence,
    )


def _result(
    score: EvaluationScore,
    retry_count: int,
    decision: EvaluationDecision,
    reason: str,
    security_signal: SecuritySignal | None,
    evidence: EvaluationEvidence | None,
) -> EvaluationResult:
    return EvaluationResult(
        score=score,
        final_score=score.final_score,
        decision=decision,
        retry_count=retry_count,
        reason=reason,
        security_signal=security_signal,
        evidence=evidence or EvaluationEvidence(),
    )


def re_evaluate_with_context(
    result: EvaluationResult,
    context: ContextPackage,
    *,
    test_refs: list[str],
) -> EvaluationResult:
    evidence = EvaluationEvidence(
        context_refs=context.evidence_refs,
        test_refs=test_refs,
        decision_refs=[f"retrieval:{context.decision}"],
        verification_source_decision=context.decision,
    )
    if context.decision == "quarantine":
        return _result(
            result.score,
            result.retry_count,
            "quarantine",
            "verification context is quarantined",
            result.security_signal,
            evidence,
        )
    if context.decision == "stop":
        return _result(
            result.score,
            result.retry_count,
            "stop",
            "verification context stopped by retrieval safety",
            result.security_signal,
            evidence,
        )
    if context.decision != "continue" or not context.evidence_refs:
        return _result(
            result.score,
            result.retry_count,
            "verify",
            "verification context still needs evidence",
            result.security_signal,
            evidence,
        )
    verified_score = result.score.model_copy(
        update={"evidence_quality": max(result.score.evidence_quality, 0.60)}
    )
    return evaluate(
        verified_score,
        retry_count=result.retry_count,
        security_signal=result.security_signal,
        evidence=evidence,
    )


def re_evaluate_after_confirmation(
    result: EvaluationResult,
    resolution: ConfirmationResolution,
) -> EvaluationResult:
    if resolution.next_state != "RESUME_AGENT_RUN":
        return result
    evidence = result.evidence.model_copy(
        update={
            "decision_refs": [
                *result.evidence.decision_refs,
                f"confirmation:{resolution.decision}",
            ]
        }
    )
    confirmed_score = result.score.model_copy(
        update={"ambiguity": min(result.score.ambiguity, 0.39)}
    )
    return evaluate(
        confirmed_score,
        retry_count=result.retry_count,
        security_signal=result.security_signal,
        evidence=evidence,
    )


def evaluate_observation(
    observation: ObservationEvaluationInput,
    *,
    retry_count: int,
    evidence: EvaluationEvidence | None = None,
) -> EvaluationResult:
    observation_evidence = evidence or EvaluationEvidence()
    score = _observation_score(observation)
    if observation.unsafe_request:
        return _result(
            score,
            retry_count,
            "stop",
            "unsafe observation request",
            None,
            observation_evidence,
        )
    if observation.completion_ready:
        if observation_evidence.ready_for_accept:
            return _result(
                score,
                retry_count,
                "finish",
                "completion observation has evidence",
                None,
                observation_evidence,
            )
        return _result(
            score,
            retry_count,
            "verify",
            "completion observation lacks context or test evidence",
            None,
            observation_evidence,
        )
    if observation.repeated_action_count >= 3:
        return _result(
            score,
            retry_count,
            "replan",
            "repeated observation action needs a new plan",
            None,
            observation_evidence,
        )
    if observation.tool_status in {"failed", "denied", "timed_out"}:
        if retry_count < 2:
            return _result(
                score,
                retry_count,
                "retry",
                "tool observation failed before retry budget",
                None,
                observation_evidence,
            )
        return _result(
            score,
            retry_count,
            "replan",
            "tool observation failed after retry budget",
            None,
            observation_evidence,
        )
    if not observation.output_present:
        return _result(
            score,
            retry_count,
            "verify",
            "tool observation output is empty",
            None,
            observation_evidence,
        )
    return evaluate(score, retry_count=retry_count, evidence=observation_evidence)


def _observation_score(observation: ObservationEvaluationInput) -> EvaluationScore:
    if observation.completion_ready:
        return EvaluationScore(
            correctness=0.95,
            completeness=0.95,
            evidence_quality=0.90,
            requirement_match=0.95,
            test_status=1.0,
            ambiguity=0.05,
            risk=0.10,
        )
    failed = observation.tool_status in {"failed", "denied", "timed_out"}
    return EvaluationScore(
        correctness=0.25 if failed else 0.70,
        completeness=0.25 if failed else 0.65,
        evidence_quality=0.10 if not observation.output_present else 0.60,
        requirement_match=0.45 if failed else 0.70,
        test_status=0.0,
        ambiguity=0.20,
        risk=0.90 if observation.unsafe_request else 0.25,
    )


def route_evaluation(
    result: EvaluationResult,
    *,
    audit_store: InMemoryAuditStore | None = None,
) -> EvaluationRoute:
    if result.decision == "accept" and not result.evidence.ready_for_accept:
        route = EvaluationRoute(
            decision="verify",
            next_state="VERIFY_EVIDENCE",
            reason="accept decision lacks context or test evidence",
        )
    else:
        route = _decision_route(result)
    if audit_store is not None:
        audit_store.append(make_audit_event("evaluation.decision", route.next_state, route.decision))
    return route


def _decision_route(result: EvaluationResult) -> EvaluationRoute:
    next_states = {
        "accept": "DECISION_GATE",
        "retry": "MODEL_PROPOSE_PATCH",
        "replan": "PLAN",
        "finish": "DONE",
        "verify": "VERIFY_EVIDENCE",
        "ask_user": "ASK_USER",
        "quarantine": "QUARANTINE",
        "stop": "ROLLBACK",
    }
    return EvaluationRoute(
        decision=result.decision,
        next_state=next_states[result.decision],
        reason=result.reason,
    )
