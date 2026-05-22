from pathlib import Path

from ai_local.harness.developer_sprint_harness import (
    load_developer_sprint_plan,
    run_developer_sprint_harness,
    validate_developer_sprint_plan,
)


ROOT = Path(__file__).resolve().parents[2]


def test_developer_sprint_plan_cuts_phases_into_thirteen_sprints() -> None:
    plan = load_developer_sprint_plan(ROOT / "configs" / "developer_sprints.yaml")

    assert len(plan.sprints) == 13
    assert plan.sprints[0].phase == "phase_1_core_loop"
    assert plan.sprints[-1].phase == "phase_6_skills"
    assert all(functional.gate_tests for sprint in plan.sprints for functional in sprint.functionals)


def test_developer_sprint_plan_validates_functional_coverage() -> None:
    plan = load_developer_sprint_plan(ROOT / "configs" / "developer_sprints.yaml")

    assert validate_developer_sprint_plan(plan, root=ROOT) == []


def test_developer_sprint_harness_runs() -> None:
    result = run_developer_sprint_harness(
        config_path=ROOT / "configs" / "developer_sprints.yaml",
        root=ROOT,
    )

    assert result.passed
    assert result.sprint_count == 13
    assert result.functional_count == 22
