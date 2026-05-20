from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class MemoryLayerRule:
    id: str
    raw: dict[str, object]


@dataclass(frozen=True)
class MemoryLayerLevel:
    name: str
    max_hop_depth: int
    layers: list[MemoryLayerRule]
    required_to_promote: bool
    description: str


@dataclass(frozen=True)
class MemoryLayerResult:
    level: str
    passed: bool
    checked_layers: list[str]
    max_hop_depth: int
    reason: str = ""


def load_memory_layer_levels(config_path: Path) -> list[MemoryLayerLevel]:
    data = load_yaml(config_path)
    levels = data.get("memory_layer_gate_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid memory layer gate config in {config_path}"
        raise ValueError(msg)

    loaded: list[MemoryLayerLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        layers = [
            MemoryLayerRule(id=str(layer["id"]), raw=layer)
            for layer in definition.get("layers", [])
            if isinstance(layer, dict) and "id" in layer
        ]
        loaded.append(
            MemoryLayerLevel(
                name=level_name,
                max_hop_depth=int(definition["max_hop_depth"]),
                layers=layers,
                required_to_promote=bool(definition.get("required_to_promote", True)),
                description=str(definition.get("description", "")),
            )
        )
    return loaded


def validate_memory_layer_level(
    level: MemoryLayerLevel,
    *,
    max_supported_hop_depth: int,
) -> MemoryLayerResult:
    checked_layers: list[str] = []
    if level.max_hop_depth > max_supported_hop_depth:
        return MemoryLayerResult(
            level=level.name,
            passed=False,
            checked_layers=checked_layers,
            max_hop_depth=level.max_hop_depth,
            reason="level exceeds max supported hop depth",
        )
    for layer in level.layers:
        checked_layers.append(layer.id)
        if not layer.id:
            return MemoryLayerResult(
                level=level.name,
                passed=False,
                checked_layers=checked_layers,
                max_hop_depth=level.max_hop_depth,
                reason="memory layer rule has no id",
            )
    return MemoryLayerResult(
        level=level.name,
        passed=True,
        checked_layers=checked_layers,
        max_hop_depth=level.max_hop_depth,
    )


def run_memory_layer_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[MemoryLayerResult]:
    data = load_yaml(config_path)
    max_supported_hop_depth = int(data.get("max_supported_hop_depth", 20))
    results: list[MemoryLayerResult] = []
    for level in load_memory_layer_levels(config_path):
        result = validate_memory_layer_level(
            level,
            max_supported_hop_depth=max_supported_hop_depth,
        )
        results.append(result)
        if level.name == max_level:
            break
        if level.required_to_promote and not result.passed:
            break
    return results

