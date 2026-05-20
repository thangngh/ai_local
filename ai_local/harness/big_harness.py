from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class BigHarnessPolicy:
    max_steps: int
    max_tool_calls: int
    max_retries_per_patch: int
    max_hop_depth: int
    required_gates: list[str]


def load_big_harness_policy(config_path: Path) -> BigHarnessPolicy:
    data = load_yaml(config_path)
    config = data.get("big_harness", {})
    if not isinstance(config, dict):
        msg = f"Invalid big harness config in {config_path}"
        raise ValueError(msg)
    return BigHarnessPolicy(
        max_steps=int(config["max_steps"]),
        max_tool_calls=int(config["max_tool_calls"]),
        max_retries_per_patch=int(config["max_retries_per_patch"]),
        max_hop_depth=int(config["max_hop_depth"]),
        required_gates=[str(gate) for gate in config.get("required_gates", [])],
    )


def validate_big_harness_policy(policy: BigHarnessPolicy) -> list[str]:
    errors: list[str] = []
    if policy.max_steps <= 0:
        errors.append("max_steps must be positive")
    if policy.max_tool_calls <= 0:
        errors.append("max_tool_calls must be positive")
    if policy.max_retries_per_patch < 0:
        errors.append("max_retries_per_patch cannot be negative")
    if policy.max_hop_depth < 50:
        errors.append("max_hop_depth must support core agent-loop hop 50")
    for required_gate in ["agent_loop", "retrieval", "decision", "composite", "small_patch"]:
        if required_gate not in policy.required_gates:
            errors.append(f"missing required gate: {required_gate}")
    return errors

