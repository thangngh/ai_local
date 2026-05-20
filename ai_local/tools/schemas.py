from pydantic import BaseModel, ConfigDict, Field


class ToolDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    side_effect_level: str
    timeout_seconds: int = Field(ge=1)
    audit_required: bool
    approval_required: bool
    risk_level: str
