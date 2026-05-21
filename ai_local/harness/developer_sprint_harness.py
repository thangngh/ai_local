from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.global_developer_harness import load_developer_phase_coverage


@dataclass(frozen=True)
class SprintFunctional:
    id: str
    gate_tests: list[str]
    before_gate_summary: str
    after_gate_summary: str


@dataclass(frozen=True)
class DeveloperSprint:
    id: str
    phase: str
    objective: str
    functionals: list[SprintFunctional]


@dataclass(frozen=True)
class DeveloperSprintPlan:
    source_ref: str
    global_harness_config: Path
    sprints: list[DeveloperSprint]


@dataclass(frozen=True)
class DeveloperSprintHarnessResult:
    passed: bool
    sprint_count: int
    functional_count: int
    errors: list[str]


def load_developer_sprint_plan(config_path: Path) -> DeveloperSprintPlan:
    data = load_yaml(config_path)
    config = data.get("developer_sprints", {})
    if not isinstance(config, dict):
        msg = f"Invalid developer sprint config in {config_path}"
        raise ValueError(msg)
    loaded: list[DeveloperSprint] = []
    for sprint in config.get("sprints", []):
        if not isinstance(sprint, dict):
            continue
        functionals = [
            SprintFunctional(
                id=str(functional["id"]),
                gate_tests=[str(command) for command in functional.get("gate_tests", [])],
                before_gate_summary=str(functional.get("before_gate_summary", "")),
                after_gate_summary=str(functional.get("after_gate_summary", "")),
            )
            for functional in sprint.get("functionals", [])
            if isinstance(functional, dict)
        ]
        loaded.append(
            DeveloperSprint(
                id=str(sprint["id"]),
                phase=str(sprint["phase"]),
                objective=str(sprint.get("objective", "")),
                functionals=functionals,
            )
        )
    return DeveloperSprintPlan(
        source_ref=str(config.get("source_ref", "")),
        global_harness_config=Path(str(config.get("global_harness_config", ""))),
        sprints=loaded,
    )


def validate_developer_sprint_plan(
    plan: DeveloperSprintPlan,
    *,
    root: Path,
) -> list[str]:
    errors: list[str] = []
    if not plan.source_ref:
        errors.append("developer sprint source_ref is required")
    global_config = root / plan.global_harness_config
    if not global_config.exists():
        errors.append(f"global harness config is missing: {plan.global_harness_config}")
        return errors
    coverage = load_developer_phase_coverage(global_config)
    expected_functionals = {requirement.id for requirement in coverage.functional_requirements}
    seen_functionals: list[str] = []
    for sprint in plan.sprints:
        if sprint.phase not in coverage.phase_ids:
            errors.append(f"{sprint.id} has unknown phase: {sprint.phase}")
        if not sprint.objective:
            errors.append(f"{sprint.id} is missing objective")
        if not sprint.functionals:
            errors.append(f"{sprint.id} is missing functional items")
        for functional in sprint.functionals:
            seen_functionals.append(functional.id)
            if functional.id not in expected_functionals:
                errors.append(f"{sprint.id} references unknown functional: {functional.id}")
            if not functional.gate_tests:
                errors.append(f"{functional.id} is missing gate test commands")
            if not functional.before_gate_summary:
                errors.append(f"{functional.id} is missing before gate summary")
            if not functional.after_gate_summary:
                errors.append(f"{functional.id} is missing after gate summary")
    duplicates = sorted({item for item in seen_functionals if seen_functionals.count(item) > 1})
    for duplicate in duplicates:
        errors.append(f"{duplicate} appears in more than one sprint")
    missing = sorted(expected_functionals - set(seen_functionals))
    for functional_id in missing:
        errors.append(f"{functional_id} is missing from developer sprint plan")
    return errors


def run_developer_sprint_harness(
    *,
    config_path: Path,
    root: Path,
) -> DeveloperSprintHarnessResult:
    plan = load_developer_sprint_plan(config_path)
    errors = validate_developer_sprint_plan(plan, root=root)
    functional_count = sum(len(sprint.functionals) for sprint in plan.sprints)
    return DeveloperSprintHarnessResult(
        passed=not errors,
        sprint_count=len(plan.sprints),
        functional_count=functional_count,
        errors=errors,
    )
