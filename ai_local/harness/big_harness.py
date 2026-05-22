from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class BigHarnessSafetyPolicy:
    require_diff_before_write: bool
    forbid_destructive_shell: bool
    require_tests_for_code_change: bool
    rollback_on_failed_gate: bool
    retrieved_content_is_data_only: bool


@dataclass(frozen=True)
class BigHarnessConfirmationPolicy:
    ask_user_if_ambiguity_above: float
    ask_user_if_risk_above: float
    ask_user_before_public_api_change: bool
    ask_user_before_schema_migration: bool
    ask_user_before_security_sensitive_change: bool


@dataclass(frozen=True)
class BigHarnessPolicy:
    max_steps: int
    max_tool_calls: int
    max_retries_per_patch: int
    max_hop_depth: int
    required_gates: list[str]
    safety: BigHarnessSafetyPolicy
    confirmation: BigHarnessConfirmationPolicy


def load_big_harness_policy(config_path: Path) -> BigHarnessPolicy:
    data = load_yaml(config_path)
    config = data.get("big_harness", {})
    if not isinstance(config, dict):
        msg = f"Invalid big harness config in {config_path}"
        raise ValueError(msg)
    safety = config.get("safety", {})
    confirmation = config.get("confirmation", {})
    if not isinstance(safety, dict) or not isinstance(confirmation, dict):
        msg = f"Invalid big harness safety policy in {config_path}"
        raise ValueError(msg)
    return BigHarnessPolicy(
        max_steps=int(config["max_steps"]),
        max_tool_calls=int(config["max_tool_calls"]),
        max_retries_per_patch=int(config["max_retries_per_patch"]),
        max_hop_depth=int(config["max_hop_depth"]),
        required_gates=[str(gate) for gate in config.get("required_gates", [])],
        safety=BigHarnessSafetyPolicy(
            require_diff_before_write=bool(safety.get("require_diff_before_write", False)),
            forbid_destructive_shell=bool(safety.get("forbid_destructive_shell", False)),
            require_tests_for_code_change=bool(safety.get("require_tests_for_code_change", False)),
            rollback_on_failed_gate=bool(safety.get("rollback_on_failed_gate", False)),
            retrieved_content_is_data_only=bool(
                safety.get("retrieved_content_is_data_only", False)
            ),
        ),
        confirmation=BigHarnessConfirmationPolicy(
            ask_user_if_ambiguity_above=float(confirmation.get("ask_user_if_ambiguity_above", 0)),
            ask_user_if_risk_above=float(confirmation.get("ask_user_if_risk_above", 0)),
            ask_user_before_public_api_change=bool(
                confirmation.get("ask_user_before_public_api_change", False)
            ),
            ask_user_before_schema_migration=bool(
                confirmation.get("ask_user_before_schema_migration", False)
            ),
            ask_user_before_security_sensitive_change=bool(
                confirmation.get("ask_user_before_security_sensitive_change", False)
            ),
        ),
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
    if not policy.safety.require_diff_before_write:
        errors.append("diff before write safety is required")
    if not policy.safety.forbid_destructive_shell:
        errors.append("destructive shell safety is required")
    if not policy.safety.require_tests_for_code_change:
        errors.append("tests for code change safety is required")
    if not policy.safety.rollback_on_failed_gate:
        errors.append("rollback on failed gate safety is required")
    if not policy.safety.retrieved_content_is_data_only:
        errors.append("retrieved content data-only safety is required")
    if not 0 < policy.confirmation.ask_user_if_ambiguity_above <= 1:
        errors.append("ambiguity confirmation threshold must be within (0, 1]")
    if not 0 < policy.confirmation.ask_user_if_risk_above <= 1:
        errors.append("risk confirmation threshold must be within (0, 1]")
    if not policy.confirmation.ask_user_before_public_api_change:
        errors.append("public API confirmation is required")
    if not policy.confirmation.ask_user_before_schema_migration:
        errors.append("schema migration confirmation is required")
    if not policy.confirmation.ask_user_before_security_sensitive_change:
        errors.append("security-sensitive confirmation is required")
    return errors
