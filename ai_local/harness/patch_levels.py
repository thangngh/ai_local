from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class PatchLevel:
    name: str
    max_files_changed: int
    max_changed_lines: int
    max_functions_changed: int
    max_new_dependencies: int
    max_hop_depth: int
    risk_ceiling: float
    requires_confirmation: bool
    requires_focused_harness: bool
    requires_full_tests: bool
    requires_rollback_plan: bool
    allowed_change_types: list[str]
    forbidden_change_types: list[str]


def load_patch_levels(config_path: Path) -> list[PatchLevel]:
    data = load_yaml(config_path)
    levels = data.get("patch_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid patch levels config in {config_path}"
        raise ValueError(msg)

    loaded: list[PatchLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        loaded.append(
            PatchLevel(
                name=level_name,
                max_files_changed=int(definition["max_files_changed"]),
                max_changed_lines=int(definition["max_changed_lines"]),
                max_functions_changed=int(definition["max_functions_changed"]),
                max_new_dependencies=int(definition["max_new_dependencies"]),
                max_hop_depth=int(definition["max_hop_depth"]),
                risk_ceiling=float(definition["risk_ceiling"]),
                requires_confirmation=bool(definition["requires_confirmation"]),
                requires_focused_harness=bool(definition["requires_focused_harness"]),
                requires_full_tests=bool(definition["requires_full_tests"]),
                requires_rollback_plan=bool(definition["requires_rollback_plan"]),
                allowed_change_types=[str(item) for item in definition.get("allowed_change_types", [])],
                forbidden_change_types=[
                    str(item) for item in definition.get("forbidden_change_types", [])
                ],
            )
        )
    return loaded


def validate_patch_levels(levels: list[PatchLevel]) -> list[str]:
    errors: list[str] = []
    previous_hop = 0
    previous_lines = 0
    for level in levels:
        if level.max_files_changed <= 0:
            errors.append(f"{level.name}: max_files_changed must be positive")
        if level.max_changed_lines < previous_lines:
            errors.append(f"{level.name}: max_changed_lines cannot decrease")
        if level.max_hop_depth < previous_hop:
            errors.append(f"{level.name}: max_hop_depth cannot decrease")
        if level.max_new_dependencies != 0:
            errors.append(f"{level.name}: new dependencies require separate approval")
        if not level.requires_focused_harness:
            errors.append(f"{level.name}: focused harness is required")
        previous_hop = level.max_hop_depth
        previous_lines = level.max_changed_lines
    return errors
