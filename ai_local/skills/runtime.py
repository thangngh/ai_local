from ai_local.skills.loader import SkillDefinition, SkillRegistry
from ai_local.skills.models import (
    SkillDecision,
    SkillDecisionResult,
    SkillNextGate,
    SkillOutputDecision,
    SkillOutputEnvelope,
    SkillOutputHandoff,
    SkillOutputKind,
    SkillRequest,
)
from ai_local.tools.registry import ToolRegistry


def decide_skill_request(
    request: SkillRequest,
    *,
    skills: SkillRegistry,
    tools: ToolRegistry | None = None,
) -> SkillDecisionResult:
    skill = skills.find(request.skill_id)
    if skill is None:
        return _result(
            request.skill_id,
            "deny",
            "tool_registry",
            "unknown skill",
            requested_tool=request.requested_tool,
            tool_registered=False if request.requested_tool else None,
            tool_allowlisted=False if request.requested_tool else None,
        )
    if request.noise_type == "deep_policy_shadowing":
        return _skill_result(skill, "stop", "stop", "skill path shadows tool policy")
    if request.noise_type == "prompt_injection":
        return _skill_result(skill, "quarantine", "quarantine", "skill output is untrusted")
    if request.requested_tool is not None:
        permission = _tool_permission(skill, request.requested_tool, tools)
        if not permission.allowed:
            return _skill_result(
                skill,
                "deny",
                "tool_registry",
                permission.reason,
                requested_tool=request.requested_tool,
                tool_registered=permission.registered,
                tool_allowlisted=permission.allowlisted,
                tool_side_effect_level=permission.side_effect_level,
                tool_requires_approval=permission.requires_approval,
                tool_audit_required=permission.audit_required,
            )
        allowed_tool_result = _skill_result(
            skill,
            "allow",
            "tool_registry",
            permission.reason,
            requested_tool=request.requested_tool,
            tool_registered=permission.registered,
            tool_allowlisted=permission.allowlisted,
            tool_side_effect_level=permission.side_effect_level,
            tool_requires_approval=permission.requires_approval,
            tool_audit_required=permission.audit_required,
        )
    if request.memory_policy_write and not skill.trusted:
        return _skill_result(
            skill,
            "ask_user",
            "confirmation",
            "untrusted skill cannot write policy memory",
        )
    if request.noise_type == "seo_noise":
        return _skill_result(skill, "verify_rank", "evidence_rank", "search output needs rank")
    if request.noise_type == "weak_evidence":
        return _skill_result(skill, "verify_more", "knowledge_gate", "evidence is weak")
    if request.noise_type == "deep_weak_evidence":
        return _skill_result(skill, "ask_user", "confirmation", "deep weak evidence is ambiguous")
    if request.requested_tool is not None:
        return allowed_tool_result
    return _skill_result(skill, "allow", "tool_registry", "skill request is allowed")


def envelope_web_research_output(
    *,
    skill: SkillDefinition,
    query: str,
    provider: str,
    source_urls: list[str],
    evidence_summary: str,
    risk_flags: list[str] | None = None,
) -> SkillOutputEnvelope:
    return SkillOutputEnvelope(
        skill_id=skill.id,
        output_kind="search",
        query=query,
        provider=provider,
        source_urls=source_urls,
        source_refs=source_urls,
        evidence_refs=source_urls,
        evidence_summary=evidence_summary,
        risk_flags=risk_flags or [],
        recommended_next_gate="evidence_rank",
    )


def envelope_skill_output(
    *,
    skill: SkillDefinition,
    output_kind: SkillOutputKind,
    query: str,
    evidence_summary: str,
    source_refs: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    risk_flags: list[str] | None = None,
    requested_next_gate: SkillNextGate | None = None,
) -> SkillOutputEnvelope:
    return SkillOutputEnvelope(
        skill_id=skill.id,
        output_kind=output_kind,
        query=query,
        provider="skill",
        source_refs=source_refs or [],
        evidence_refs=evidence_refs or [],
        evidence_summary=evidence_summary,
        risk_flags=risk_flags or [],
        requested_next_gate=requested_next_gate,
        recommended_next_gate="evidence_rank",
    )


def route_skill_output(envelope: SkillOutputEnvelope) -> SkillOutputHandoff:
    if "deep_policy_shadowing" in envelope.risk_flags:
        return _handoff(envelope, "stop", "stop", "skill output shadows policy")
    if "prompt_injection" in envelope.risk_flags:
        return _handoff(envelope, "quarantine", "quarantine", "skill output is prompt-injected")
    if envelope.requested_next_gate in {"patch_pipeline", "decision_gate", "memory_governance"}:
        return _handoff(
            envelope,
            "ask_user",
            "confirmation",
            "skill output cannot directly authorize privileged downstream gate",
        )
    if envelope.output_kind in {"policy", "patch_request"}:
        return _handoff(
            envelope,
            "ask_user",
            "confirmation",
            "skill output needs confirmation before policy or patch handoff",
        )
    if not envelope.evidence_refs and not envelope.source_refs:
        return _handoff(envelope, "verify_more", "knowledge_gate", "skill output lacks evidence refs")
    return _handoff(
        envelope,
        "rank_evidence",
        "evidence_rank",
        "skill output is data until evidence ranked",
    )


def _handoff(
    envelope: SkillOutputEnvelope,
    decision: SkillOutputDecision,
    next_gate: SkillNextGate,
    reason: str,
) -> SkillOutputHandoff:
    return SkillOutputHandoff(
        envelope=envelope,
        decision=decision,
        next_gate=next_gate,
        reason=reason,
        requires_audit=True,
        source_ref_count=len(envelope.source_refs) + len(envelope.source_urls),
        evidence_ref_count=len(envelope.evidence_refs),
        privileged_request=_is_privileged_output(envelope),
    )


def _is_privileged_output(envelope: SkillOutputEnvelope) -> bool:
    return envelope.output_kind in {"policy", "patch_request"} or envelope.requested_next_gate in {
        "memory_governance",
        "decision_gate",
        "patch_pipeline",
    }


class _ToolPermission:
    def __init__(
        self,
        *,
        allowed: bool,
        reason: str,
        registered: bool,
        allowlisted: bool,
        side_effect_level: str | None = None,
        requires_approval: bool | None = None,
        audit_required: bool | None = None,
    ) -> None:
        self.allowed = allowed
        self.reason = reason
        self.registered = registered
        self.allowlisted = allowlisted
        self.side_effect_level = side_effect_level
        self.requires_approval = requires_approval
        self.audit_required = audit_required


def _tool_permission(
    skill: SkillDefinition,
    tool_name: str,
    tools: ToolRegistry | None,
) -> _ToolPermission:
    allowlisted = tool_name in skill.allowed_tools
    tool = tools.find(tool_name) if tools is not None else None
    registered = tool is not None if tools is not None else True
    side_effect_level = tool.side_effect_level if tool is not None else None
    requires_approval = tool.approval_required if tool is not None else None
    audit_required = tool.audit_required if tool is not None else None
    if not allowlisted:
        return _ToolPermission(
            allowed=False,
            reason="skill tool is not allowlisted",
            registered=registered,
            allowlisted=False,
            side_effect_level=side_effect_level,
            requires_approval=requires_approval,
            audit_required=audit_required,
        )
    if not registered:
        return _ToolPermission(
            allowed=False,
            reason="skill tool is not registered",
            registered=False,
            allowlisted=True,
        )
    if not skill.trusted and side_effect_level in {"write", "process"}:
        return _ToolPermission(
            allowed=False,
            reason="untrusted skill cannot invoke side-effect tool directly",
            registered=True,
            allowlisted=True,
            side_effect_level=side_effect_level,
            requires_approval=requires_approval,
            audit_required=audit_required,
        )
    if not skill.trusted and requires_approval:
        return _ToolPermission(
            allowed=False,
            reason="untrusted skill cannot request approval-gated tool directly",
            registered=True,
            allowlisted=True,
            side_effect_level=side_effect_level,
            requires_approval=requires_approval,
            audit_required=audit_required,
        )
    return _ToolPermission(
        allowed=True,
        reason="skill tool is allowed",
        registered=registered,
        allowlisted=True,
        side_effect_level=side_effect_level,
        requires_approval=requires_approval,
        audit_required=audit_required,
    )


def _skill_result(
    skill: SkillDefinition,
    decision: SkillDecision,
    next_gate: SkillNextGate,
    reason: str,
    *,
    requested_tool: str | None = None,
    tool_registered: bool | None = None,
    tool_allowlisted: bool | None = None,
    tool_side_effect_level: str | None = None,
    tool_requires_approval: bool | None = None,
    tool_audit_required: bool | None = None,
) -> SkillDecisionResult:
    return _result(
        skill.id,
        decision,
        next_gate,
        reason,
        allowed_tools=skill.allowed_tools,
        trusted=skill.trusted,
        risk_level=skill.risk_level,
        requested_tool=requested_tool,
        tool_registered=tool_registered,
        tool_allowlisted=tool_allowlisted,
        tool_side_effect_level=tool_side_effect_level,
        tool_requires_approval=tool_requires_approval,
        tool_audit_required=tool_audit_required,
    )


def _result(
    skill_id: str,
    decision: SkillDecision,
    next_gate: SkillNextGate,
    reason: str,
    *,
    allowed_tools: list[str] | None = None,
    trusted: bool = False,
    risk_level: str = "unknown",
    requested_tool: str | None = None,
    tool_registered: bool | None = None,
    tool_allowlisted: bool | None = None,
    tool_side_effect_level: str | None = None,
    tool_requires_approval: bool | None = None,
    tool_audit_required: bool | None = None,
) -> SkillDecisionResult:
    return SkillDecisionResult(
        skill_id=skill_id,
        decision=decision,
        next_gate=next_gate,
        reason=reason,
        allowed_tools=allowed_tools or [],
        trusted=trusted,
        risk_level=risk_level,
        requested_tool=requested_tool,
        tool_registered=tool_registered,
        tool_allowlisted=tool_allowlisted,
        tool_side_effect_level=tool_side_effect_level,
        tool_requires_approval=tool_requires_approval,
        tool_audit_required=tool_audit_required,
    )
