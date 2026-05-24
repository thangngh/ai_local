from typing import Literal

from pydantic import BaseModel, Field


MemoryLevel = Literal[
    "M0_SESSION_SCRATCH",
    "M1_PERSONAL_PREFERENCE",
    "M2_PROJECT_CONVENTION",
    "M3_CONFIRMED_DECISION",
    "M4_WORKFLOW_MEMORY",
    "M5_SAFETY_POLICY",
]
MemoryScope = Literal["session", "global", "project", "repo"]
MemoryStatus = Literal["candidate", "active", "stale", "archived", "quarantined"]
MemorySensitivity = Literal["public", "internal", "sensitive", "secret"]
MemoryEvidenceType = Literal["user_confirmation", "project_doc", "test", "usage", "source_hash"]
MemoryWriteDecision = Literal[
    "accept",
    "accept_memory",
    "verify",
    "reject_memory",
    "reject_policy_promotion",
    "ask_user",
    "quarantine",
    "stop",
]
MemoryRetrievalDecision = Literal[
    "inject_memory",
    "verify_before_use",
    "do_not_use",
    "drop",
    "demote",
    "demote_stale",
    "prefer_confirmed_memory",
    "archive_memory",
]
MemorySqlNoise = Literal[
    "none",
    "scope_noise",
    "weak_project_evidence",
    "wrong_scope",
    "conflicting_memory",
    "stale_source_hash",
    "inferred_policy",
    "deep_memory_poisoning",
    "safety_policy_laundering",
]


class MemoryItem(BaseModel):
    claim: str
    scope: MemoryScope
    source: str
    confidence: float = Field(ge=0.0, le=1.0)
    risk: float = Field(default=0.0, ge=0.0, le=1.0)
    memory_level: MemoryLevel = "M1_PERSONAL_PREFERENCE"
    status: MemoryStatus = "candidate"
    evidence_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    retrieval_score: float = Field(default=0.0, ge=0.0, le=1.0)
    conflict_score: float = Field(default=0.0, ge=0.0, le=1.0)
    usage_success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    confirmed: bool = False
    fresh: bool = True
    secret_like: bool = False
    inferred_policy: bool = False
    source_hash_changed: bool = False
    harmful_usage: bool = False
    evidence_refs: list[str] = Field(default_factory=list)
    conflict_refs: list[str] = Field(default_factory=list)
    role: str = "assistant"
    sensitivity: MemorySensitivity = "public"
    confirmed_by: str | None = None
    source_hash: str | None = None
    last_used_at: str | None = None

    @property
    def has_explicit_evidence(self) -> bool:
        return bool(self.evidence_refs or self.confirmed_by)


class MemoryEvidenceRecord(BaseModel):
    memory_id: str = Field(min_length=1)
    evidence_type: MemoryEvidenceType
    ref: str = Field(min_length=1)
    summary: str = ""
    weight: float = Field(default=0.0, ge=0.0, le=1.0)


class MemoryConflictRecord(BaseModel):
    memory_id: str = Field(min_length=1)
    conflicting_memory_id: str = Field(min_length=1)
    conflict_score: float = Field(ge=0.0, le=1.0)
    reason: str
    status: Literal["open", "resolved", "ignored"] = "open"


class MemoryUsageRecord(BaseModel):
    memory_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    retrieval_score: float = Field(ge=0.0, le=1.0)
    used_as: str
    outcome: Literal["success", "verify", "harmful", "ignored"]


class MemoryDecision(BaseModel):
    item: MemoryItem
    decision: MemoryWriteDecision | MemoryRetrievalDecision
    reason: str


class MemoryDocMatchSignal(BaseModel):
    semantic_match: float = Field(ge=0.0, le=1.0)
    flow_match: float = Field(ge=0.0, le=1.0)
    evidence_match: float = Field(ge=0.0, le=1.0)
    scope_match: float = Field(ge=0.0, le=1.0)
    interference: float = Field(default=0.0, ge=0.0, le=1.0)
    laundered: bool = False
    conflicted: bool = False


RegressionDecision = Literal["restore", "verify_before_use", "reject_laundered_match"]


class MemoryRegressionResult(BaseModel):
    active_state: str = Field(min_length=1)
    state_hops: int = Field(ge=0)
    doc_match_score: float = Field(ge=-1.0, le=1.0)
    constraints_restored: int = Field(ge=0)
    constraints_required: int = Field(ge=0)
    decision: RegressionDecision
