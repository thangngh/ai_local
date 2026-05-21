from typing import Literal

from pydantic import BaseModel, Field


KnowledgeLevel = Literal[
    "K0_UNKNOWN",
    "K1_BASIC",
    "K2_PROJECT",
    "K3_CURRENT",
    "K4_ADVANCED",
    "K5_GROUND_TRUTH",
    "K6_DECISION_POLICY",
]
KnowledgeNoise = Literal[
    "none",
    "unsupported_claim",
    "noisy_repo_comments",
    "stale_docs",
    "best_practice_conflict",
    "prompt_injection",
    "conflicting_project_docs",
    "deep_policy_laundering",
    "current_api_uncertainty",
]
KnowledgeDecision = Literal["use", "verify_more", "ask_user", "quarantine", "reject"]
EvidenceNoise = Literal[
    "none",
    "unknown_source",
    "noisy_comments",
    "stale_docs",
    "conflicting_sources",
    "prompt_injection",
    "policy_laundering",
    "repeated_untrusted_claim",
    "deep_context_noise",
]
EvidenceBand = Literal["canonical", "strong", "caution", "weak", "reject"]
ConflictDecision = Literal["ask_user", "defer_until_evidence", "stop"]
ConflictType = Literal[
    "equal_authority_equal_evidence",
    "multi_instance_tie",
    "missing_test_evidence",
    "no_safe_path",
    "circular_confirmation",
    "unresolved_equivalence_class",
    "all_paths_invalid",
]


class KnowledgeItem(BaseModel):
    claim: str
    level: KnowledgeLevel
    source_ref: str
    confidence: float = Field(ge=0.0, le=1.0)
    rank: int = Field(ge=0, le=100)
    evidence_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    conflict_score: float = Field(default=0.0, ge=0.0, le=1.0)
    noise_type: KnowledgeNoise = "none"


class KnowledgeGateDecision(BaseModel):
    item: KnowledgeItem
    decision: KnowledgeDecision
    reason: str


class EvidenceSignal(BaseModel):
    source_authority: int = Field(ge=0, le=30)
    evidence_strength: int = Field(ge=0, le=25)
    freshness: int = Field(ge=0, le=15)
    project_relevance: int = Field(ge=0, le=15)
    confirmation_weight: int = Field(ge=0, le=15)
    conflict_penalty: int = Field(default=0, ge=0, le=100)
    staleness_penalty: int = Field(default=0, ge=0, le=100)
    noise_type: EvidenceNoise = "none"


class EvidenceRank(BaseModel):
    signal: EvidenceSignal
    rank: int = Field(ge=-200, le=100)
    band: EvidenceBand
    reason: str


class ConflictCandidate(BaseModel):
    id: str = Field(min_length=1)
    evidence_rank: int = Field(ge=0, le=100)
    risk: float = Field(ge=0.0, le=1.0)
    authority: str = Field(min_length=1)


class ConflictResolution(BaseModel):
    conflict_type: ConflictType
    candidates: list[ConflictCandidate] = Field(min_length=2)
    decision: ConflictDecision
    reason: str
