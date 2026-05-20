from pydantic import BaseModel, Field


class MemoryItem(BaseModel):
    claim: str
    scope: str
    source: str
    confidence: float = Field(ge=0.0, le=1.0)
    risk: float = Field(default=0.0, ge=0.0, le=1.0)

