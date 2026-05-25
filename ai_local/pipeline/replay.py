from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from ai_local.config.loader import load_yaml
from ai_local.pipeline.report import Phase9ReportScenario, run_phase9_integration_report


@dataclass(frozen=True)
class Phase9ReplayFixture:
    id: str
    scenario: Phase9ReportScenario
    expected_status: str
    expected_final_state: str
    expected_patch_decision: str | None
    expected_skill_decision: str | None
    expected_output_ready: bool
    expected_hop_depth: int
    expected_noise_profile: str
    expected_conflict_profile: str
    required_stages: list[str] = field(default_factory=list)
    forbidden_stages: list[str] = field(default_factory=list)
    required_evidence_prefixes: list[str] = field(default_factory=list)
    required_risk_flags: list[str] = field(default_factory=list)
    forbidden_risk_flags: list[str] = field(default_factory=list)
    required_reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Phase9ReplayResult:
    fixture_id: str
    scenario: Phase9ReportScenario
    passed: bool
    status: str
    final_state: str
    reasons: list[str]
    chain_id: str | None = None


def load_phase9_replay_fixtures(config_path: Path) -> list[Phase9ReplayFixture]:
    data = load_yaml(config_path)
    fixtures = data.get("fixtures", [])
    if not isinstance(fixtures, list):
        msg = f"Invalid replay fixture config in {config_path}"
        raise ValueError(msg)
    return [_fixture_from_mapping(item) for item in fixtures if isinstance(item, dict)]


def run_phase9_replay_fixtures(
    *,
    config_path: Path,
    workspace_root: Path,
    patch_levels_config: Path,
    audit_db: Path | None = None,
) -> list[Phase9ReplayResult]:
    return [
        run_phase9_replay_fixture(
            fixture,
            workspace_root=workspace_root,
            patch_levels_config=patch_levels_config,
            audit_db=audit_db,
        )
        for fixture in load_phase9_replay_fixtures(config_path)
    ]


def run_phase9_replay_fixture(
    fixture: Phase9ReplayFixture,
    *,
    workspace_root: Path,
    patch_levels_config: Path,
    audit_db: Path | None = None,
) -> Phase9ReplayResult:
    report = run_phase9_integration_report(
        scenario=fixture.scenario,
        workspace_root=workspace_root,
        patch_levels_config=patch_levels_config,
        audit_db=audit_db,
    )
    reasons = _compare_fixture(fixture, report)
    return Phase9ReplayResult(
        fixture_id=fixture.id,
        scenario=fixture.scenario,
        passed=not reasons,
        status=str(report["status"]),
        final_state=str(report["final_state"]),
        reasons=reasons,
        chain_id=str(report["chain_id"]) if "chain_id" in report else None,
    )


def _compare_fixture(fixture: Phase9ReplayFixture, report: dict[str, object]) -> list[str]:
    errors: list[str] = []
    _expect(errors, fixture.id, "status", fixture.expected_status, report["status"])
    _expect(errors, fixture.id, "final_state", fixture.expected_final_state, report["final_state"])
    _expect(
        errors,
        fixture.id,
        "patch_decision",
        fixture.expected_patch_decision,
        report["patch_decision"],
    )
    _expect(
        errors,
        fixture.id,
        "skill_decision",
        fixture.expected_skill_decision,
        report["skill_decision"],
    )
    _expect(
        errors,
        fixture.id,
        "output_ready",
        fixture.expected_output_ready,
        report["output_ready"],
    )
    _expect(errors, fixture.id, "hop_depth", fixture.expected_hop_depth, report["hop_depth"])
    _expect(
        errors,
        fixture.id,
        "noise_profile",
        fixture.expected_noise_profile,
        report["noise_profile"],
    )
    _expect(
        errors,
        fixture.id,
        "conflict_profile",
        fixture.expected_conflict_profile,
        report["conflict_profile"],
    )

    stages = _string_list(report["stages"])
    evidence_refs = _string_list(report["evidence_refs"])
    risk_flags = _string_list(report["risk_flags"])
    reasons = _string_list(report["reasons"])

    errors.extend(_missing_items(fixture.id, "required stage", fixture.required_stages, stages))
    errors.extend(_present_items(fixture.id, "forbidden stage", fixture.forbidden_stages, stages))
    errors.extend(_missing_prefixes(fixture.id, fixture.required_evidence_prefixes, evidence_refs))
    errors.extend(_missing_items(fixture.id, "required risk", fixture.required_risk_flags, risk_flags))
    errors.extend(_present_items(fixture.id, "forbidden risk", fixture.forbidden_risk_flags, risk_flags))
    errors.extend(_missing_substrings(fixture.id, fixture.required_reasons, reasons))
    return errors


def _fixture_from_mapping(item: dict[object, object]) -> Phase9ReplayFixture:
    scenario = str(item["scenario"])
    if scenario not in {"ready", "no-path", "prompt-injection"}:
        msg = f"Unsupported Phase 9 replay scenario: {scenario}"
        raise ValueError(msg)
    return Phase9ReplayFixture(
        id=str(item["id"]),
        scenario=cast(Phase9ReportScenario, scenario),
        expected_status=str(item["expected_status"]),
        expected_final_state=str(item["expected_final_state"]),
        expected_patch_decision=_optional_str(item.get("expected_patch_decision")),
        expected_skill_decision=_optional_str(item.get("expected_skill_decision")),
        expected_output_ready=bool(item["expected_output_ready"]),
        expected_hop_depth=_int_value(item["expected_hop_depth"]),
        expected_noise_profile=str(item["expected_noise_profile"]),
        expected_conflict_profile=str(item["expected_conflict_profile"]),
        required_stages=_list_of_str(item.get("required_stages")),
        forbidden_stages=_list_of_str(item.get("forbidden_stages")),
        required_evidence_prefixes=_list_of_str(item.get("required_evidence_prefixes")),
        required_risk_flags=_list_of_str(item.get("required_risk_flags")),
        forbidden_risk_flags=_list_of_str(item.get("forbidden_risk_flags")),
        required_reasons=_list_of_str(item.get("required_reasons")),
    )


def _expect(
    errors: list[str],
    fixture_id: str,
    field_name: str,
    expected: object,
    actual: object,
) -> None:
    if actual != expected:
        errors.append(f"{fixture_id}: expected {field_name}={expected!r}, got {actual!r}")


def _missing_items(
    fixture_id: str,
    label: str,
    expected: list[str],
    actual: list[str],
) -> list[str]:
    actual_set = set(actual)
    return [f"{fixture_id}: missing {label}: {item}" for item in expected if item not in actual_set]


def _present_items(
    fixture_id: str,
    label: str,
    forbidden: list[str],
    actual: list[str],
) -> list[str]:
    actual_set = set(actual)
    return [f"{fixture_id}: present {label}: {item}" for item in forbidden if item in actual_set]


def _missing_prefixes(
    fixture_id: str,
    expected_prefixes: list[str],
    actual: list[str],
) -> list[str]:
    return [
        f"{fixture_id}: missing evidence prefix: {prefix}"
        for prefix in expected_prefixes
        if not any(ref.startswith(prefix) for ref in actual)
    ]


def _missing_substrings(
    fixture_id: str,
    expected_substrings: list[str],
    actual: list[str],
) -> list[str]:
    return [
        f"{fixture_id}: missing reason containing: {substring}"
        for substring in expected_substrings
        if not any(substring in reason for reason in actual)
    ]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _list_of_str(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        msg = "Expected list value in Phase 9 replay fixture"
        raise ValueError(msg)
    return [str(item) for item in value]


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    msg = f"Expected int-like value, got {type(value).__name__}"
    raise ValueError(msg)
