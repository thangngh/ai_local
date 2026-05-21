from pydantic import BaseModel, ConfigDict, Field


class ToolDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    side_effect_level: str
    timeout_seconds: int = Field(ge=1)
    audit_required: bool
    approval_required: bool
    risk_level: str


class ToolCall(BaseModel):
    name: str
    args: dict[str, object] = Field(default_factory=dict)
    approved: bool = False


class ToolResult(BaseModel):
    tool_name: str
    status: str
    output: dict[str, object] = Field(default_factory=dict)
    error: str | None = None
    audited: bool = False
