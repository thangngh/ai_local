from ai_local.evaluator.models import (
    EvaluationDecision,
    EvaluationResult,
    EvaluationScore,
    SecuritySignal,
)


def decide(score: EvaluationScore, retry_count: int) -> str:
    return evaluate(score, retry_count=retry_count).decision


def evaluate(
    score: EvaluationScore,
    *,
    retry_count: int,
    security_signal: SecuritySignal | None = None,
) -> EvaluationResult:
    if security_signal == "deep_policy_shadowing" or score.risk >= 0.85:
        return _result(score, retry_count, "stop", "risk ceiling reached", security_signal)
    if security_signal == "tool_policy_override":
        return _result(score, retry_count, "quarantine", "tool policy override", security_signal)
    if security_signal == "memory_conflict":
        return _result(score, retry_count, "verify", "memory evidence conflicts", security_signal)
    if score.ambiguity >= 0.60:
        return _result(score, retry_count, "ask_user", "ambiguity requires confirmation", security_signal)
    if security_signal == "laundered_evidence":
        return _result(score, retry_count, "ask_user", "evidence authority is unclear", security_signal)
    if score.evidence_quality <= 0.40:
        return _result(score, retry_count, "verify", "evidence quality below floor", security_signal)
    if score.requirement_match <= 0.40:
        return _retry_or_ask(score, retry_count, "requirement match below floor", security_signal)
    if score.final_score >= 0.80 and score.risk < 0.50 and score.test_status >= 0.50:
        return _result(score, retry_count, "accept", "score and risk thresholds passed", security_signal)
    if score.final_score >= 0.60:
        return _retry_or_ask(score, retry_count, "score needs another patch attempt", security_signal)
    return _result(score, retry_count, "ask_user", "score cannot promote automatically", security_signal)


def _retry_or_ask(
    score: EvaluationScore,
    retry_count: int,
    reason: str,
    security_signal: SecuritySignal | None,
) -> EvaluationResult:
    if retry_count < 2:
        return _result(score, retry_count, "retry", reason, security_signal)
    return _result(score, retry_count, "ask_user", f"{reason}; retry budget exhausted", security_signal)


def _result(
    score: EvaluationScore,
    retry_count: int,
    decision: EvaluationDecision,
    reason: str,
    security_signal: SecuritySignal | None,
) -> EvaluationResult:
    return EvaluationResult(
        score=score,
        final_score=score.final_score,
        decision=decision,
        retry_count=retry_count,
        reason=reason,
        security_signal=security_signal,
    )
