from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    name: str
    description: str
    allowed_tools: list[str]
    risk_level: str
    trusted: bool
    body: str


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
