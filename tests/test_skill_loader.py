from pathlib import Path

from ai_local.skills.loader import parse_skill_markdown


ROOT = Path(__file__).resolve().parents[1]


def test_parse_web_research_skill() -> None:
    skill = parse_skill_markdown(ROOT / "skills" / "web-research" / "SKILL.md")

    assert skill.id == "web-research"
    assert skill.trusted is False
    assert "web_search" in skill.allowed_tools

