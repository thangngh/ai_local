from pydantic import BaseModel, Field


class PlanItem(BaseModel):
    intent: str
    required_tools: list[str] = Field(default_factory=list)
    risk_level: str = "low"

