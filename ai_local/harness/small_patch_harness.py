from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class SmallPatchLevel:
    name: str
    max_files_changed: int
    max_changed_lines: int
    max_hop_depth: int
    required_evidence: list[str]
    required_checks: list[str]


@dataclass(frozen=True)
class SmallPatchResult:
    level: str
    passed: bool
    reason: str = ""


def load_small_patch_levels(config_path: Path) -> list[SmallPatchLevel]:
    data = load_yaml(config_path)
    harness = data.get("small_patch_harness", {})
    if not isinstance(harness, dict):
        msg = f"Invalid small patch harness config in {config_path}"
        raise ValueError(msg)
    levels = harness.get("levels", {})
    if not isinstance(levels, dict):
        return []
    return [
        SmallPatchLevel(
            name=str(name),
            max_files_changed=int(definition["max_files_changed"]),
            max_changed_lines=int(definition["max_changed_lines"]),
            max_hop_depth=int(definition["max_hop_depth"]),
            required_evidence=[str(item) for item in definition.get("required_evidence", [])],
            required_checks=[str(item) for item in definition.get("required_checks", [])],
        )
        for name, definition in levels.items()
        if isinstance(definition, dict)
    ]


def validate_small_patch_level(level: SmallPatchLevel) -> SmallPatchResult:
    if level.max_files_changed <= 0:
        return SmallPatchResult(level=level.name, passed=False, reason="max_files_changed invalid")
    if level.max_changed_lines <= 0:
        return SmallPatchResult(level=level.name, passed=False, reason="max_changed_lines invalid")
    if "requirement_id" not in level.required_evidence:
        return SmallPatchResult(level=level.name, passed=False, reason="requirement_id evidence missing")
    if "test.harness" not in level.required_checks:
        return SmallPatchResult(level=level.name, passed=False, reason="focused harness check missing")
    return SmallPatchResult(level=level.name, passed=True)


def run_small_patch_policy_check(config_path: Path) -> list[SmallPatchResult]:
    return [validate_small_patch_level(level) for level in load_small_patch_levels(config_path)]

