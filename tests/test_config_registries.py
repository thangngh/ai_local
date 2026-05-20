from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.tools.registry import ToolRegistry


ROOT = Path(__file__).resolve().parents[1]


def test_skills_registry_has_requirement_first_flow() -> None:
    data = load_yaml(ROOT / "configs" / "skills.yaml")
    skill_ids = [skill["id"] for skill in data["skills"]]

    assert skill_ids[:4] == [
        "requirements.parse",
        "requirements.normalize",
        "harness.generate",
        "harness.review",
    ]
    assert "patch.apply" in skill_ids
    assert skill_ids.index("harness.review") < skill_ids.index("patch.apply")


def test_requirements_parse_fetches_all_configured_sources() -> None:
    data = load_yaml(ROOT / "configs" / "skills.yaml")
    parse_skill = next(skill for skill in data["skills"] if skill["id"] == "requirements.parse")

    assert len(parse_skill["default_source_urls"]) == 4
    assert "all_configured_sources_fetched" in parse_skill["gates"]


def test_tool_registry_loads_yaml_definitions() -> None:
    registry = ToolRegistry.from_yaml(ROOT / "configs" / "tools.yaml")

    assert "notion.fetch" in registry.names()
    assert "test.pytest" in registry.names()
    assert registry.get("filesystem.patch").risk_level == "high"

