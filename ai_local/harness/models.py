from pydantic import BaseModel, Field


class HarnessCommand(BaseModel):
    id: str
    argv: list[str] = Field(min_length=1)
    timeout_seconds: int = Field(default=60, ge=1)


class PatchGate(BaseModel):
    patch_id: str
    focused_commands: list[str] = Field(default_factory=list)
    broad_commands: list[str] = Field(default_factory=list)


class GateLevel(BaseModel):
    name: str
    commands: list[str] = Field(default_factory=list)
    required_to_promote: bool = True
    description: str = ""
