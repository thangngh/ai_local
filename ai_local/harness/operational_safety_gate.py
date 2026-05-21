from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class OperationalSafetyCase:
    id: str
    flow: list[str]
    scenario: str
    expected_decision: str
    hop_depth: int


@dataclass(frozen=True)
class OperationalSafetyLevel:
    name: str
    max_hop_depth: int
    cases: list[OperationalSafetyCase]
    required_to_promote: bool
    description: str


@dataclass(frozen=True)
class OperationalSafetyResult:
    level: str
    passed: bool
    checked_case_ids: list[str]
    max_hop_depth: int
    reason: str = ""


def parse_operational_flow(flow: str) -> list[str]:
    return [stage.strip() for stage in flow.split("->") if stage.strip()]


def infer_operational_decision(case: OperationalSafetyCase) -> str:
    decisions = {
        "worker_crash_reclaim": "reclaim_job",
        "concurrent_write_run": "wait_for_write_lock",
        "approved_side_effect": "enqueue_outbox_event",
        "duplicate_idempotency_key": "dispatch_once",
        "prompt_policy_override": "quarantine_context",
        "approval_missing": "hold_for_approval",
        "denied_secret_path": "deny_and_audit",
        "crash_after_decision": "replay_outbox_dispatch",
        "retry_budget_exhausted": "dead_letter_job",
    }
    return decisions.get(case.scenario, "stop")


def load_operational_safety_levels(config_path: Path) -> list[OperationalSafetyLevel]:
    data = load_yaml(config_path)
    levels = data.get("operational_safety_gate_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid operational safety config in {config_path}"
        raise ValueError(msg)

    loaded: list[OperationalSafetyLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        max_hop_depth = int(definition["max_hop_depth"])
        cases = [
            OperationalSafetyCase(
                id=str(case["id"]),
                flow=parse_operational_flow(str(case["flow"])),
                scenario=str(case["scenario"]),
                expected_decision=str(case["expected_decision"]),
                hop_depth=int(case.get("hop_depth", max_hop_depth)),
            )
            for case in definition.get("cases", [])
            if isinstance(case, dict)
        ]
        loaded.append(
            OperationalSafetyLevel(
                name=level_name,
                max_hop_depth=max_hop_depth,
                cases=cases,
                required_to_promote=bool(definition.get("required_to_promote", True)),
                description=str(definition.get("description", "")),
            )
        )
    return loaded


def run_operational_safety_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[OperationalSafetyResult]:
    data = load_yaml(config_path)
    known_modules = set(data.get("operational_modules", []))
    results: list[OperationalSafetyResult] = []
    for level in load_operational_safety_levels(config_path):
        checked: list[str] = []
        passed = True
        reason = ""
        for case in level.cases:
            checked.append(case.id)
            if case.hop_depth > level.max_hop_depth:
                passed = False
                reason = f"{case.id} exceeds max hop depth"
                break
            unknown = [stage for stage in case.flow if stage not in known_modules]
            if unknown:
                passed = False
                reason = f"{case.id} has unknown operational modules: {unknown}"
                break
            actual = infer_operational_decision(case)
            if actual != case.expected_decision:
                passed = False
                reason = f"{case.id} expected {case.expected_decision}, got {actual}"
                break
        result = OperationalSafetyResult(level.name, passed, checked, level.max_hop_depth, reason)
        results.append(result)
        if level.name == max_level:
            break
        if level.required_to_promote and not passed:
            break
    return results
