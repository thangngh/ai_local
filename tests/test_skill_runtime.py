from pathlib import Path

from ai_local.skills.loader import SkillRegistry
from ai_local.skills.models import SkillRequest
from ai_local.skills.runtime import decide_skill_request, envelope_web_research_output
from ai_local.tools.registry import ToolRegistry


ROOT = Path(__file__).resolve().parents[1]


def _skills() -> SkillRegistry:
    return SkillRegistry.from_gate_config(ROOT / "configs" / "skill_gates.yaml", root=ROOT)


def test_skill_registry_loads_web_research_metadata() -> None:
    skill = _skills().get("web-research")

    assert skill.id == "web-research"
    assert not skill.trusted
    assert skill.allowed_tools == ["web_search", "evidence_rank", "knowledge.search"]


def test_skill_runtime_enforces_tool_allowlist_and_policy_confirmation() -> None:
    tools = ToolRegistry.from_yaml(ROOT / "configs" / "tools.yaml")
    allowed = decide_skill_request(
        SkillRequest(skill_id="web-research", requested_tool="web_search"),
        skills=_skills(),
        tools=tools,
    )
    denied = decide_skill_request(
        SkillRequest(skill_id="web-research", requested_tool="filesystem.patch"),
        skills=_skills(),
        tools=tools,
    )
    policy_write = decide_skill_request(
        SkillRequest(skill_id="web-research", memory_policy_write=True),
        skills=_skills(),
        tools=tools,
    )

    assert (allowed.decision, allowed.next_gate) == ("allow", "tool_registry")
    assert denied.decision == "deny"
    assert (policy_write.decision, policy_write.next_gate) == ("ask_user", "confirmation")


def test_skill_runtime_routes_evidence_and_security_noise() -> None:
    assert decide_skill_request(
        SkillRequest(skill_id="web-research", noise_type="seo_noise"),
        skills=_skills(),
    ).decision == "verify_rank"
    assert decide_skill_request(
        SkillRequest(skill_id="web-research", noise_type="weak_evidence"),
        skills=_skills(),
    ).decision == "verify_more"
    assert decide_skill_request(
        SkillRequest(skill_id="web-research", noise_type="prompt_injection"),
        skills=_skills(),
    ).decision == "quarantine"
    assert decide_skill_request(
        SkillRequest(skill_id="web-research", noise_type="deep_policy_shadowing"),
        skills=_skills(),
    ).decision == "stop"


def test_web_research_output_stays_data_until_evidence_ranked() -> None:
    envelope = envelope_web_research_output(
        skill=_skills().get("web-research"),
        query="FastAPI lifespan docs",
        provider="duckduckgo",
        source_urls=["https://example.test/fastapi"],
        evidence_summary="Search result points to documentation.",
        risk_flags=["search_result"],
    )

    assert envelope.skill_id == "web-research"
    assert envelope.recommended_next_gate == "evidence_rank"
    assert envelope.source_urls == ["https://example.test/fastapi"]
