from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    name: str
    description: str
    allowed_tools: list[str]
    risk_level: str
    trusted: bool
    body: str


class SkillRegistry:
    def __init__(self, definitions: dict[str, SkillDefinition]) -> None:
        self._definitions = definitions

    @classmethod
    def from_gate_config(cls, config_path: Path, *, root: Path) -> "SkillRegistry":
        data = load_yaml(config_path)
        registered = data.get("registered_skills", {})
        if not isinstance(registered, dict):
            return cls({})
        definitions: dict[str, SkillDefinition] = {}
        for skill_id, definition in registered.items():
            if not isinstance(skill_id, str) or not isinstance(definition, dict):
                continue
            path = definition.get("path")
            if isinstance(path, str):
                definitions[skill_id] = parse_skill_markdown(root / path)
        return cls(definitions)

    def get(self, skill_id: str) -> SkillDefinition:
        return self._definitions[skill_id]

    def find(self, skill_id: str) -> SkillDefinition | None:
        return self._definitions.get(skill_id)

    def names(self) -> list[str]:
        return sorted(self._definitions)


def parse_skill_markdown(path: Path) -> SkillDefinition:
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        msg = f"Skill {path} missing frontmatter"
        raise ValueError(msg)
    _, frontmatter, body = content.split("---", 2)
    metadata = parse_simple_frontmatter(frontmatter)
    allowed_tools = metadata.get("allowed_tools", [])
    if not isinstance(allowed_tools, list):
        allowed_tools = []
    return SkillDefinition(
        id=str(metadata["id"]),
        name=str(metadata["name"]),
        description=str(metadata["description"]),
        allowed_tools=[str(tool) for tool in allowed_tools],
        risk_level=str(metadata["risk_level"]),
        trusted=bool(metadata.get("trusted", False)),
        body=body.strip(),
    )


def parse_simple_frontmatter(frontmatter: str) -> dict[str, object]:
    metadata: dict[str, object] = {}
    current_list_key: str | None = None
    for raw_line in frontmatter.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped.startswith("- ") and current_list_key:
            value = stripped[2:].strip()
            existing = metadata.setdefault(current_list_key, [])
            if isinstance(existing, list):
                existing.append(value)
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value == "":
                metadata[key] = []
                current_list_key = key
            elif value.lower() in {"true", "false"}:
                metadata[key] = value.lower() == "true"
                current_list_key = None
            else:
                metadata[key] = value
                current_list_key = None
    return metadata
