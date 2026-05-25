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
    "request_lifecycle",
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
SkillPackageTrustDecision = Literal["allow", "deny", "quarantine"]
SkillScriptDecision = Literal["allow", "deny", "ask_user", "quarantine"]
SkillScriptRunDecision = Literal[
    "succeeded",
    "failed",
    "timed_out",
    "denied",
    "ask_user",
    "quarantine",
]
SkillLifecycleAction = Literal["install", "update"]
SkillLifecycleDecision = Literal[
    "allow_install",
    "allow_update",
    "rollback",
    "deny",
    "quarantine",
]
SkillInstallDecision = Literal["installed", "updated", "rolled_back", "denied", "quarantined"]


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


class SkillRuntimeEvidenceHandoff(BaseModel):
    envelope: SkillOutputEnvelope
    decision: SkillOutputDecision
    next_gate: SkillNextGate
    reason: str
    evidence_rank: int
    evidence_band: str
    audit_refs: list[str] = Field(default_factory=list)
    requires_audit: bool = True


class SkillPackageManifest(BaseModel):
    package_id: str | None = None
    skill_id: str | None = None
    source_ref: str | None = None
    checksum: str | None = None
    trusted: bool | None = None
    signed: bool = False
    manifest_identity: str | None = None
    risk_level: str = "unknown"


class SkillPackageTrustResult(BaseModel):
    package_id: str | None
    skill_id: str | None
    decision: SkillPackageTrustDecision
    reason: str
    source_ref: str | None = None
    checksum: str | None = None
    trusted: bool = False
    signed: bool = False
    install_audit_required: bool = True


class SkillScriptRequest(BaseModel):
    package: SkillPackageTrustResult
    script_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    declared_tools: list[str] = Field(default_factory=list)
    approved: bool = False
    allow_trusted_side_effects: bool = False
    output_has_evidence_refs: bool = False


class SkillScriptSandboxResult(BaseModel):
    package_id: str | None
    script_id: str
    tool_name: str
    decision: SkillScriptDecision
    reason: str
    tool_registered: bool
    tool_declared: bool
    side_effect_level: str | None = None
    requires_approval: bool = False
    audit_required: bool = True
    next_gate: SkillNextGate


class SkillScriptRunRequest(BaseModel):
    script: SkillScriptRequest
    argv: list[str] = Field(default_factory=list)
    cwd: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=1)


class SkillScriptRunResult(BaseModel):
    package_id: str | None
    script_id: str
    tool_name: str
    decision: SkillScriptRunDecision
    reason: str
    command: list[str] = Field(default_factory=list)
    cwd: str | None = None
    timeout_seconds: int | None = None
    stdout: str = ""
    stderr: str = ""
    return_code: int | None = None
    audit_required: bool = True
    next_gate: SkillNextGate


class SkillLifecycleRequest(BaseModel):
    action: SkillLifecycleAction
    package: SkillPackageTrustResult
    controlled_root: str | None = None
    manifest_inspected: bool = False
    frontmatter_valid: bool = False
    checksum_verified: bool = False
    source_verified: bool = False
    risk_classified: bool = False
    previous_package_id: str | None = None
    rollback_available: bool = False
    lifecycle_failure_detected: bool = False
    policy_shadowing_detected: bool = False


class SkillLifecycleResult(BaseModel):
    package_id: str | None
    skill_id: str | None
    action: SkillLifecycleAction
    decision: SkillLifecycleDecision
    reason: str
    controlled_root: str | None = None
    rollback_required: bool = False
    audit_required: bool = True
    next_gate: SkillNextGate


class SkillInstallRequest(BaseModel):
    lifecycle: SkillLifecycleResult
    source_dir: str = Field(min_length=1)
    staging_root: str = Field(min_length=1)
    controlled_root: str = Field(min_length=1)
    package_dir_name: str | None = None
    simulate_failure: bool = False


class SkillInstallResult(BaseModel):
    package_id: str | None
    skill_id: str | None
    decision: SkillInstallDecision
    reason: str
    target_dir: str | None = None
    staging_dir: str | None = None
    rollback_dir: str | None = None
    audit_required: bool = True
    next_gate: SkillNextGate
