from pathlib import Path

from ai_local.config.loader import load_yaml


ROOT = Path(__file__).resolve().parents[2]


def test_requirement_sources_are_configured_for_extraction() -> None:
    skills = load_yaml(ROOT / "configs" / "skills.yaml")
    tools = load_yaml(ROOT / "configs" / "tools.yaml")

    parse_skill = next(skill for skill in skills["skills"] if skill["id"] == "requirements.parse")
    source_urls = parse_skill["default_source_urls"]

    assert source_urls == tools["tools"]["notion.fetch"]["default_urls"]
    assert len(source_urls) == 4

