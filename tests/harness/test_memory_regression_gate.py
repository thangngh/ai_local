from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.memory_regression_gate import (
    count_state_hops,
    load_memory_regression_levels,
    run_memory_regression_promotion,
)


ROOT = Path(__file__).resolve().parents[2]


def test_memory_regression_levels_promote_from_easy_to_extreme() -> None:
    levels = load_memory_regression_levels(ROOT / "configs" / "memory_regression_gates.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert [level.max_state_hops for level in levels] == [2, 4, 6, 8]


def test_state_hop_count_tracks_nonlinear_transitions() -> None:
    assert count_state_hops("a") == 0
    assert count_state_hops("a-b-a") == 2
    assert count_state_hops("a-b-c-b-c-d-a") == 6


def test_memory_regression_checks_do_not_exceed_hop_limits() -> None:
    levels = load_memory_regression_levels(ROOT / "configs" / "memory_regression_gates.yaml")

    for level in levels:
        assert level.checks
        assert all(count_state_hops(check.pattern) <= level.max_state_hops for check in level.checks)


def test_doc_match_formula_and_required_fields_are_defined() -> None:
    data = load_yaml(ROOT / "configs" / "memory_regression_gates.yaml")

    assert "semantic_match" in data["doc_match"]["formula"]
    assert data["doc_match"]["required_fields"] == [
        "source_ref",
        "evidence",
        "flow",
        "scope",
        "role",
        "status",
    ]


def test_memory_regression_promotion_passes_static_gate_definitions() -> None:
    results = run_memory_regression_promotion(
        config_path=ROOT / "configs" / "memory_regression_gates.yaml"
    )

    assert [result.level for result in results] == ["easy", "medium", "hard", "extreme"]
    assert all(result.passed for result in results)
