from ai_local.skills.loader import SkillDefinition, SkillRegistry
from ai_local.skills.models import (
    SkillDecision,
    SkillDecisionResult,
    SkillNextGate,
    SkillOutputEnvelope,
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
        return _result(request.skill_id, "deny", "tool_registry", "unknown skill")
    if request.noise_type == "deep_policy_shadowing":
        return _skill_result(skill, "stop", "stop", "skill path shadows tool policy")
    if request.noise_type == "prompt_injection":
        return _skill_result(skill, "quarantine", "quarantine", "skill output is untrusted")
    if request.requested_tool is not None and not _tool_allowed(skill, request.requested_tool, tools):
        return _skill_result(skill, "deny", "tool_registry", "skill tool is not allowlisted")
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
        query=query,
        provider=provider,
        source_urls=source_urls,
        evidence_summary=evidence_summary,
        risk_flags=risk_flags or [],
        recommended_next_gate="evidence_rank",
    )


def _tool_allowed(skill: SkillDefinition, tool_name: str, tools: ToolRegistry | None) -> bool:
    if tool_name not in skill.allowed_tools:
        return False
    return tools is None or tools.find(tool_name) is not None


def _skill_result(
    skill: SkillDefinition,
    decision: SkillDecision,
    next_gate: SkillNextGate,
    reason: str,
) -> SkillDecisionResult:
    return _result(
        skill.id,
        decision,
        next_gate,
        reason,
        allowed_tools=skill.allowed_tools,
    )


def _result(
    skill_id: str,
    decision: SkillDecision,
    next_gate: SkillNextGate,
    reason: str,
    *,
    allowed_tools: list[str] | None = None,
) -> SkillDecisionResult:
    return SkillDecisionResult(
        skill_id=skill_id,
        decision=decision,
        next_gate=next_gate,
        reason=reason,
        allowed_tools=allowed_tools or [],
    )
