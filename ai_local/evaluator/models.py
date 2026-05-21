from typing import Literal

from pydantic import BaseModel, Field


EvaluationDecision = Literal["accept", "retry", "verify", "ask_user", "quarantine", "stop"]
SecuritySignal = Literal[
    "deep_policy_shadowing",
    "tool_policy_override",
    "memory_conflict",
    "laundered_evidence",
]


class EvaluationScore(BaseModel):
    correctness: float = Field(ge=0.0, le=1.0)
    completeness: float = Field(ge=0.0, le=1.0)
    evidence_quality: float = Field(ge=0.0, le=1.0)
    requirement_match: float = Field(ge=0.0, le=1.0)
    test_status: float = Field(ge=0.0, le=1.0)
    ambiguity: float = Field(ge=0.0, le=1.0)
    risk: float = Field(ge=0.0, le=1.0)

    @property
    def final_score(self) -> float:
        return (
            0.25 * self.correctness
            + 0.20 * self.completeness
            + 0.20 * self.evidence_quality
            + 0.15 * self.requirement_match
            + 0.10 * self.test_status
            - 0.10 * self.ambiguity
            - 0.10 * self.risk
        )


class EvaluationResult(BaseModel):
    score: EvaluationScore
    final_score: float = Field(ge=-1.0, le=1.0)
    decision: EvaluationDecision
    retry_count: int = Field(ge=0)
    reason: str
    security_signal: SecuritySignal | None = None
