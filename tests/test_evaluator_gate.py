from ai_local.evaluator.models import EvaluationScore
from ai_local.evaluator.service import decide


def test_decision_gate_accepts_high_score_low_risk() -> None:
    score = EvaluationScore(
        correctness=1.0,
        completeness=1.0,
        evidence_quality=1.0,
        requirement_match=1.0,
        test_status=1.0,
        ambiguity=0.0,
        risk=0.0,
    )

    assert decide(score, retry_count=0) == "accept"


def test_decision_gate_stops_unsafe_patch() -> None:
    score = EvaluationScore(
        correctness=1.0,
        completeness=1.0,
        evidence_quality=1.0,
        requirement_match=1.0,
        test_status=1.0,
        ambiguity=0.0,
        risk=0.9,
    )

    assert decide(score, retry_count=0) == "stop"

