from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class NoiseCheck:
    id: str
    source_type: str
    hop_depth: int
    expected_decision: str


@dataclass(frozen=True)
class NoiseGateLevel:
    name: str
    max_hop_depth: int
    checks: list[NoiseCheck]
    required_to_promote: bool
    description: str


@dataclass(frozen=True)
class NoiseGateResult:
    level: str
    passed: bool
    checked_ids: list[str]
    max_hop_depth: int
    reason: str = ""


def load_noise_gate_levels(config_path: Path) -> list[NoiseGateLevel]:
    data = load_yaml(config_path)
    levels = data.get("noise_gate_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid noise gate config in {config_path}"
        raise ValueError(msg)

    loaded: list[NoiseGateLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        checks = [
            NoiseCheck(
                id=str(check["id"]),
                source_type=str(check["source_type"]),
                hop_depth=int(check["hop_depth"]),
                expected_decision=str(check["expected_decision"]),
            )
            for check in definition.get("checks", [])
            if isinstance(check, dict)
        ]
        loaded.append(
            NoiseGateLevel(
                name=level_name,
                max_hop_depth=int(definition["max_hop_depth"]),
                checks=checks,
                required_to_promote=bool(definition.get("required_to_promote", True)),
                description=str(definition.get("description", "")),
            )
        )
    return loaded


def validate_noise_level(level: NoiseGateLevel) -> NoiseGateResult:
    checked_ids: list[str] = []
    for check in level.checks:
        checked_ids.append(check.id)
        if check.hop_depth < 1:
            return NoiseGateResult(
                level=level.name,
                passed=False,
                checked_ids=checked_ids,
                max_hop_depth=level.max_hop_depth,
                reason=f"{check.id} has invalid hop depth",
            )
        if check.hop_depth > level.max_hop_depth:
            return NoiseGateResult(
                level=level.name,
                passed=False,
                checked_ids=checked_ids,
                max_hop_depth=level.max_hop_depth,
                reason=f"{check.id} exceeds max hop depth",
            )
        if not check.expected_decision:
            return NoiseGateResult(
                level=level.name,
                passed=False,
                checked_ids=checked_ids,
                max_hop_depth=level.max_hop_depth,
                reason=f"{check.id} has no expected decision",
            )
    return NoiseGateResult(
        level=level.name,
        passed=True,
        checked_ids=checked_ids,
        max_hop_depth=level.max_hop_depth,
    )


def run_noise_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[NoiseGateResult]:
    results: list[NoiseGateResult] = []
    for level in load_noise_gate_levels(config_path):
        result = validate_noise_level(level)
        results.append(result)
        if level.name == max_level:
            break
        if level.required_to_promote and not result.passed:
            break
    return results

