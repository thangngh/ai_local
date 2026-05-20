from pydantic import BaseModel, Field


class KnowledgeItem(BaseModel):
    claim: str
    level: str
    source_ref: str
    confidence: float = Field(ge=0.0, le=1.0)
    rank: int = Field(ge=0, le=100)

