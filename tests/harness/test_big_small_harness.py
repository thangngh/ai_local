from pathlib import Path

from ai_local.harness.big_harness import load_big_harness_policy, validate_big_harness_policy
from ai_local.harness.small_patch_harness import (
    load_small_patch_levels,
    run_small_patch_policy_check,
)


ROOT = Path(__file__).resolve().parents[2]


def test_big_harness_requires_core_gates_and_hop_50() -> None:
    policy = load_big_harness_policy(ROOT / "configs" / "big_harness.yaml")

    assert policy.max_hop_depth == 50
    assert "agent_loop" in policy.required_gates
    assert "small_patch" in policy.required_gates
    assert policy.safety.require_diff_before_write
    assert policy.safety.retrieved_content_is_data_only
    assert policy.confirmation.ask_user_if_risk_above == 0.70
    assert policy.confirmation.ask_user_before_security_sensitive_change
    assert validate_big_harness_policy(policy) == []


def test_small_patch_levels_scale_easy_to_extreme() -> None:
    levels = load_small_patch_levels(ROOT / "configs" / "small_patch_harness.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert [level.max_hop_depth for level in levels] == [5, 12, 25, 50]


def test_small_patch_policy_requires_harness_and_requirement() -> None:
    results = run_small_patch_policy_check(ROOT / "configs" / "small_patch_harness.yaml")

    assert all(result.passed for result in results)
