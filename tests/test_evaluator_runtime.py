from ai_local.evaluator.models import EvaluationScore
from ai_local.evaluator.service import evaluate


def _score(**overrides: float) -> EvaluationScore:
    values = {
        "correctness": 1.0,
        "completeness": 1.0,
        "evidence_quality": 1.0,
        "requirement_match": 1.0,
        "test_status": 1.0,
        "ambiguity": 0.1,
        "risk": 0.1,
    }
    values.update(overrides)
    return EvaluationScore(**values)


def test_evaluator_returns_score_reason_and_accept_decision() -> None:
    result = evaluate(_score(), retry_count=0)

    assert result.decision == "accept"
    assert result.final_score == result.score.final_score
    assert result.reason == "score and risk thresholds passed"


def test_evaluator_verifies_weak_evidence_before_accepting_score() -> None:
    result = evaluate(_score(evidence_quality=0.2), retry_count=0)

    assert result.decision == "verify"
    assert result.reason == "evidence quality below floor"


def test_evaluator_security_signals_choose_protected_paths() -> None:
    assert evaluate(_score(), retry_count=0, security_signal="tool_policy_override").decision == (
        "quarantine"
    )
    assert evaluate(_score(), retry_count=0, security_signal="memory_conflict").decision == "verify"
    assert evaluate(_score(), retry_count=0, security_signal="deep_policy_shadowing").decision == (
        "stop"
    )


def test_evaluator_stops_retrying_after_budget() -> None:
    result = evaluate(_score(correctness=0.65, completeness=0.65), retry_count=2)

    assert result.decision == "ask_user"
    assert "retry budget exhausted" in result.reason
