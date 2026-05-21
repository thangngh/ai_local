from pathlib import Path

from ai_local.harness.global_developer_harness import (
    load_developer_phase_coverage,
    run_global_developer_harness,
    validate_developer_phase_coverage,
)


ROOT = Path(__file__).resolve().parents[2]


def test_global_developer_harness_covers_main_notion_phases() -> None:
    coverage = load_developer_phase_coverage(ROOT / "configs" / "global_developer_harness.yaml")

    assert coverage.phase_ids == [
        "phase_1_core_loop",
        "phase_2_retrieval",
        "phase_3_harness",
        "phase_4_evaluation",
        "phase_5_knowledge",
        "phase_6_skills",
    ]
    assert len(coverage.functional_requirements) == 12
    assert all(requirement.gate_harnesses for requirement in coverage.functional_requirements)


def test_global_developer_harness_validates_gate_inventory() -> None:
    coverage = load_developer_phase_coverage(ROOT / "configs" / "global_developer_harness.yaml")

    assert validate_developer_phase_coverage(coverage, root=ROOT) == []


def test_global_developer_harness_runs() -> None:
    result = run_global_developer_harness(
        config_path=ROOT / "configs" / "global_developer_harness.yaml",
        root=ROOT,
    )

    assert result.passed
    assert result.functional_count == 12
    assert result.non_functional_count == 6
    assert result.gate_count >= 25
