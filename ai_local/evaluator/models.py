from pydantic import BaseModel, Field


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

