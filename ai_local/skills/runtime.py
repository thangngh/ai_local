from ai_local.audit.store import InMemoryAuditStore, make_audit_event
from ai_local.skills.loader import SkillDefinition, SkillRegistry
from ai_local.skills.models import (
    SkillDecision,
    SkillDecisionResult,
    SkillLifecycleDecision,
    SkillLifecycleRequest,
    SkillLifecycleResult,
    SkillNextGate,
    SkillOutputDecision,
    SkillOutputEnvelope,
    SkillOutputHandoff,
    SkillOutputKind,
    SkillPackageManifest,
    SkillPackageTrustDecision,
    SkillPackageTrustResult,
    SkillRequest,
    SkillScriptDecision,
    SkillScriptRequest,
    SkillScriptSandboxResult,
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


def verify_skill_package(
    manifest: SkillPackageManifest,
    *,
    expected_checksum: str | None = None,
    allowed_source_prefixes: list[str] | None = None,
    audit_store: InMemoryAuditStore | None = None,
) -> SkillPackageTrustResult:
    result = _verify_skill_package(
        manifest,
        expected_checksum=expected_checksum,
        allowed_source_prefixes=allowed_source_prefixes or [],
    )
    if audit_store is not None:
        audit_store.append(
            make_audit_event(
                "skill.package.verify",
                result.package_id or "unknown-package",
                result.decision,
            )
        )
    return result


def evaluate_skill_script(
    request: SkillScriptRequest,
    *,
    tools: ToolRegistry,
    audit_store: InMemoryAuditStore | None = None,
) -> SkillScriptSandboxResult:
    result = _evaluate_skill_script(request, tools=tools)
    if audit_store is not None:
        audit_store.append(
            make_audit_event(
                "skill.script.policy",
                f"{request.package.package_id or 'unknown-package'}:{request.script_id}",
                result.decision,
            )
        )
    return result


def evaluate_skill_lifecycle(
    request: SkillLifecycleRequest,
    *,
    audit_store: InMemoryAuditStore | None = None,
) -> SkillLifecycleResult:
    result = _evaluate_skill_lifecycle(request)
    if audit_store is not None:
        audit_store.append(
            make_audit_event(
                f"skill.lifecycle.{request.action}",
                request.package.package_id or "unknown-package",
                result.decision,
            )
        )
    return result


def _evaluate_skill_lifecycle(request: SkillLifecycleRequest) -> SkillLifecycleResult:
    package = request.package
    if package.decision == "quarantine" or request.policy_shadowing_detected:
        return _lifecycle_result(
            request,
            "quarantine",
            "package lifecycle contains policy shadowing",
            next_gate="quarantine",
        )
    if package.decision != "allow" or not package.trusted:
        return _lifecycle_result(
            request,
            "deny",
            "install lifecycle requires verified package trust",
            next_gate="tool_registry",
        )
    if not request.controlled_root:
        return _lifecycle_result(
            request,
            "deny",
            "install lifecycle requires controlled skill root",
            next_gate="tool_registry",
        )
    if not request.manifest_inspected:
        return _lifecycle_result(
            request,
            "deny",
            "install lifecycle requires manifest inspection",
            next_gate="knowledge_gate",
        )
    if not request.frontmatter_valid:
        return _lifecycle_result(
            request,
            "deny",
            "install lifecycle requires valid skill frontmatter",
            next_gate="knowledge_gate",
        )
    if not request.checksum_verified:
        return _lifecycle_result(
            request,
            "deny",
            "install lifecycle requires checksum verification",
            next_gate="evidence_rank",
        )
    if not request.source_verified:
        return _lifecycle_result(
            request,
            "deny",
            "install lifecycle requires source verification",
            next_gate="evidence_rank",
        )
    if not request.risk_classified:
        return _lifecycle_result(
            request,
            "deny",
            "install lifecycle requires risk classification",
            next_gate="decision_gate",
        )
    if request.lifecycle_failure_detected:
        if request.rollback_available:
            return _lifecycle_result(
                request,
                "rollback",
                "lifecycle failure requires rollback",
                next_gate="patch_pipeline",
                rollback_required=True,
            )
        return _lifecycle_result(
            request,
            "deny",
            "lifecycle failure has no rollback path",
            next_gate="stop",
        )
    if request.action == "update":
        if not request.previous_package_id:
            return _lifecycle_result(
                request,
                "deny",
                "update lifecycle requires previous package audit reference",
                next_gate="request_lifecycle",
            )
        if not request.rollback_available:
            return _lifecycle_result(
                request,
                "deny",
                "update lifecycle requires rollback availability",
                next_gate="patch_pipeline",
            )
        return _lifecycle_result(
            request,
            "allow_update",
            "skill update lifecycle verified",
            next_gate="evidence_rank",
        )
    return _lifecycle_result(
        request,
        "allow_install",
        "skill install lifecycle verified",
        next_gate="evidence_rank",
    )


def _lifecycle_result(
    request: SkillLifecycleRequest,
    decision: SkillLifecycleDecision,
    reason: str,
    *,
    next_gate: SkillNextGate,
    rollback_required: bool = False,
) -> SkillLifecycleResult:
    return SkillLifecycleResult(
        package_id=request.package.package_id,
        skill_id=request.package.skill_id,
        action=request.action,
        decision=decision,
        reason=reason,
        controlled_root=request.controlled_root,
        rollback_required=rollback_required,
        audit_required=True,
        next_gate=next_gate,
    )


def _evaluate_skill_script(
    request: SkillScriptRequest,
    *,
    tools: ToolRegistry,
) -> SkillScriptSandboxResult:
    package = request.package
    if package.decision == "quarantine":
        return _script_result(
            request,
            "quarantine",
            "package trust is quarantined",
            tools=tools,
            next_gate="quarantine",
        )
    if package.decision != "allow" or not package.trusted:
        return _script_result(
            request,
            "deny",
            "scripts are disabled unless package trust is verified",
            tools=tools,
            next_gate="tool_registry",
        )
    tool = tools.find(request.tool_name)
    if tool is None:
        return _script_result(
            request,
            "deny",
            "script tool is not registered",
            tools=tools,
            next_gate="tool_registry",
        )
    if request.tool_name not in request.declared_tools:
        return _script_result(
            request,
            "deny",
            "script tool is not declared by package policy",
            tools=tools,
            next_gate="tool_registry",
        )
    if tool.side_effect_level in {"write", "process", "network"} and not (
        request.approved or request.allow_trusted_side_effects
    ):
        return _script_result(
            request,
            "ask_user",
            "script side effect requires approval or trusted package policy",
            tools=tools,
            next_gate="confirmation",
        )
    next_gate: SkillNextGate = "evidence_rank" if request.output_has_evidence_refs else "knowledge_gate"
    reason = (
        "script output is data until evidence ranked"
        if request.output_has_evidence_refs
        else "script output lacks evidence refs"
    )
    return _script_result(request, "allow", reason, tools=tools, next_gate=next_gate)


def _script_result(
    request: SkillScriptRequest,
    decision: SkillScriptDecision,
    reason: str,
    *,
    tools: ToolRegistry,
    next_gate: SkillNextGate,
) -> SkillScriptSandboxResult:
    tool = tools.find(request.tool_name)
    return SkillScriptSandboxResult(
        package_id=request.package.package_id,
        script_id=request.script_id,
        tool_name=request.tool_name,
        decision=decision,
        reason=reason,
        tool_registered=tool is not None,
        tool_declared=request.tool_name in request.declared_tools,
        side_effect_level=tool.side_effect_level if tool is not None else None,
        requires_approval=bool(tool and tool.approval_required),
        audit_required=True,
        next_gate=next_gate,
    )


def _verify_skill_package(
    manifest: SkillPackageManifest,
    *,
    expected_checksum: str | None,
    allowed_source_prefixes: list[str],
) -> SkillPackageTrustResult:
    missing = [
        field
        for field, value in {
            "package_id": manifest.package_id,
            "skill_id": manifest.skill_id,
            "source_ref": manifest.source_ref,
            "checksum": manifest.checksum,
            "manifest_identity": manifest.manifest_identity,
        }.items()
        if not value
    ]
    if missing:
        return _package_result(manifest, "deny", f"package manifest missing {missing[0]}")
    if manifest.trusted is None:
        return _package_result(manifest, "deny", "package trust state is missing")
    if _contains_policy_shadowing(manifest):
        return _package_result(manifest, "quarantine", "package manifest contains policy shadowing")
    if allowed_source_prefixes and not any(
        str(manifest.source_ref).startswith(prefix) for prefix in allowed_source_prefixes
    ):
        return _package_result(manifest, "deny", "package source is not trusted")
    if expected_checksum is not None and manifest.checksum != expected_checksum:
        return _package_result(manifest, "deny", "package checksum mismatch")
    if not manifest.trusted:
        return _package_result(manifest, "deny", "package is untrusted")
    if manifest.manifest_identity != manifest.skill_id:
        return _package_result(manifest, "deny", "manifest identity does not match skill id")
    return _package_result(manifest, "allow", "package trust verified")


def _contains_policy_shadowing(manifest: SkillPackageManifest) -> bool:
    joined = " ".join(
        value.lower()
        for value in [
            manifest.package_id,
            manifest.skill_id,
            manifest.source_ref,
            manifest.manifest_identity,
        ]
        if value
    )
    blocked = ("ignore policy", "override policy", "disable gate", "bypass approval")
    return any(term in joined for term in blocked)


def _package_result(
    manifest: SkillPackageManifest,
    decision: SkillPackageTrustDecision,
    reason: str,
) -> SkillPackageTrustResult:
    return SkillPackageTrustResult(
        package_id=manifest.package_id,
        skill_id=manifest.skill_id,
        decision=decision,
        reason=reason,
        source_ref=manifest.source_ref,
        checksum=manifest.checksum,
        trusted=bool(manifest.trusted),
        signed=manifest.signed,
        install_audit_required=True,
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
