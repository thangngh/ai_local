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
    "memory_governance",
    "decision_gate",
    "patch_pipeline",
    "confirmation",
    "quarantine",
    "stop",
]
SkillOutputKind = Literal["workflow", "search", "analysis", "policy", "patch_request"]
SkillOutputDecision = Literal[
    "rank_evidence",
    "verify_more",
    "ask_user",
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
    trusted: bool = False
    risk_level: str = "unknown"
    requested_tool: str | None = None
    tool_registered: bool | None = None
    tool_allowlisted: bool | None = None
    tool_side_effect_level: str | None = None
    tool_requires_approval: bool | None = None
    tool_audit_required: bool | None = None


class SkillOutputEnvelope(BaseModel):
    skill_id: str
    output_kind: SkillOutputKind = "search"
    query: str = Field(min_length=1)
    provider: str = "skill"
    source_urls: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    evidence_summary: str = Field(min_length=1)
    risk_flags: list[str] = Field(default_factory=list)
    requested_next_gate: SkillNextGate | None = None
    recommended_next_gate: SkillNextGate = "evidence_rank"


class SkillOutputHandoff(BaseModel):
    envelope: SkillOutputEnvelope
    decision: SkillOutputDecision
    next_gate: SkillNextGate
    reason: str
    requires_audit: bool = True
    source_ref_count: int = Field(ge=0)
    evidence_ref_count: int = Field(ge=0)
    privileged_request: bool = False
