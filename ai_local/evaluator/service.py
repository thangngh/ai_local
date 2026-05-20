from ai_local.evaluator.models import EvaluationScore


def decide(score: EvaluationScore, retry_count: int) -> str:
    if score.risk > 0.85:
        return "stop"
    if score.ambiguity > 0.60:
        return "ask_user"
    if score.final_score >= 0.80 and score.risk < 0.50:
        return "accept"
    if score.final_score >= 0.60 and retry_count < 2:
        return "retry"
    return "ask_user"

