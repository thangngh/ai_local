from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.tools.schemas import ToolDefinition


class ToolRegistry:
    def __init__(self, definitions: dict[str, ToolDefinition]) -> None:
        self._definitions = definitions

    @classmethod
    def from_yaml(cls, path: Path) -> "ToolRegistry":
        data = load_yaml(path)
        tools = data.get("tools", {})
        definitions = {
            name: ToolDefinition(name=name, **definition) for name, definition in tools.items()
        }
        return cls(definitions)

    def get(self, name: str) -> ToolDefinition:
        return self._definitions[name]

    def names(self) -> list[str]:
        return sorted(self._definitions)

