from typing import Literal

from pydantic import BaseModel, Field


SkillNoise = Literal[
    "none",
    "tool_allowlist",
    "seo_noise",
    "weak_evidence",
    "prompt_injection",
    "unlisted_tool_request",
    "untrusted_policy_write",
    "deep_policy_shadowing",
    "deep_weak_evidence",
]
SkillDecision = Literal[
    "allow",
    "deny",
    "verify_rank",
    "verify_more",
    "quarantine",
    "ask_user",
    "stop",
]
SkillNextGate = Literal[
    "tool_registry",
    "evidence_rank",
    "knowledge_gate",
    "confirmation",
    "quarantine",
    "stop",
]


class SkillRequest(BaseModel):
    skill_id: str = Field(min_length=1)
    requested_tool: str | None = None
    memory_policy_write: bool = False
    noise_type: SkillNoise = "none"


class SkillDecisionResult(BaseModel):
    skill_id: str
    decision: SkillDecision
    next_gate: SkillNextGate
    reason: str
    allowed_tools: list[str] = Field(default_factory=list)


class SkillOutputEnvelope(BaseModel):
    skill_id: str
    query: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    source_urls: list[str] = Field(min_length=1)
    evidence_summary: str = Field(min_length=1)
    risk_flags: list[str] = Field(default_factory=list)
    recommended_next_gate: SkillNextGate = "evidence_rank"
