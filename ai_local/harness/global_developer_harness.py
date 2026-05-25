from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class DeveloperRequirement:
    id: str
    name: str
    gate_harnesses: list[str]
    phase: str | None = None


@dataclass(frozen=True)
class DeveloperPhaseCoverage:
    source_ref: str
    phase_ids: list[str]
    functional_requirements: list[DeveloperRequirement]
    non_functional_requirements: list[DeveloperRequirement]
    known_gate_harnesses: dict[str, Path]


@dataclass(frozen=True)
class GlobalDeveloperHarnessResult:
    passed: bool
    functional_count: int
    non_functional_count: int
    gate_count: int
    errors: list[str]


def _load_requirements(items: object, *, needs_phase: bool) -> list[DeveloperRequirement]:
    if not isinstance(items, list):
        return []
    requirements: list[DeveloperRequirement] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        phase = str(item["phase"]) if needs_phase and "phase" in item else None
        requirements.append(
            DeveloperRequirement(
                id=str(item["id"]),
                name=str(item["name"]),
                gate_harnesses=[str(gate) for gate in item.get("gate_harnesses", [])],
                phase=phase,
            )
        )
    return requirements


def load_developer_phase_coverage(config_path: Path) -> DeveloperPhaseCoverage:
    data = load_yaml(config_path)
    phase = data.get("developer_phase", {})
    known = data.get("known_gate_harnesses", {})
    if not isinstance(phase, dict) or not isinstance(known, dict):
        msg = f"Invalid global developer harness config in {config_path}"
        raise ValueError(msg)
    phases = phase.get("phases", [])
    phase_ids = [
        str(item["id"])
        for item in phases
        if isinstance(item, dict) and "id" in item
    ]
    return DeveloperPhaseCoverage(
        source_ref=str(phase.get("source_ref", "")),
        phase_ids=phase_ids,
        functional_requirements=_load_requirements(
            phase.get("functional_requirements", []),
            needs_phase=True,
        ),
        non_functional_requirements=_load_requirements(
            phase.get("non_functional_requirements", []),
            needs_phase=False,
        ),
        known_gate_harnesses={str(gate): Path(str(path)) for gate, path in known.items()},
    )


def validate_developer_phase_coverage(
    coverage: DeveloperPhaseCoverage,
    *,
    root: Path,
) -> list[str]:
    errors: list[str] = []
    if not coverage.source_ref:
        errors.append("developer phase source_ref is required")
    if coverage.phase_ids != [
        "phase_1_core_loop",
        "phase_2_retrieval",
        "phase_3_harness",
        "phase_4_evaluation",
        "phase_5_knowledge",
        "phase_6_skills",
        "phase_7_skill_distribution",
        "phase_8_skill_runtime",
    ]:
        errors.append("developer phase order must match the configured developer phases")
    for requirement in coverage.functional_requirements:
        if requirement.phase not in coverage.phase_ids:
            errors.append(f"{requirement.id} has unknown phase: {requirement.phase}")
        if not requirement.gate_harnesses:
            errors.append(f"{requirement.id} is missing gate harness coverage")
    for requirement in coverage.non_functional_requirements:
        if not requirement.gate_harnesses:
            errors.append(f"{requirement.id} is missing non-functional gate coverage")
    for requirement in [
        *coverage.functional_requirements,
        *coverage.non_functional_requirements,
    ]:
        for gate in requirement.gate_harnesses:
            if gate not in coverage.known_gate_harnesses:
                errors.append(f"{requirement.id} references unknown gate: {gate}")
    for gate, path in coverage.known_gate_harnesses.items():
        if not (root / path).exists():
            errors.append(f"{gate} runner is missing: {path}")
    return errors


def run_global_developer_harness(
    *,
    config_path: Path,
    root: Path,
) -> GlobalDeveloperHarnessResult:
    coverage = load_developer_phase_coverage(config_path)
    errors = validate_developer_phase_coverage(coverage, root=root)
    return GlobalDeveloperHarnessResult(
        passed=not errors,
        functional_count=len(coverage.functional_requirements),
        non_functional_count=len(coverage.non_functional_requirements),
        gate_count=len(coverage.known_gate_harnesses),
        errors=errors,
    )
