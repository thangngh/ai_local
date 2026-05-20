from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class CompositeGate:
    id: str
    level: str
    modules: list[str]
    flow: str
    max_hop_depth: int
    noise_profile: str
    required_evidence: list[str]
    expected_decision: str


@dataclass(frozen=True)
class CompositeGateResult:
    level: str
    passed: bool
    checked_gate_ids: list[str]
    max_hop_depth: int
    reason: str = ""


def load_composite_gates(config_path: Path) -> list[CompositeGate]:
    data = load_yaml(config_path)
    gates = data.get("composite_gates", [])
    if not isinstance(gates, list):
        msg = f"Invalid composite gate config in {config_path}"
        raise ValueError(msg)
    return [
        CompositeGate(
            id=str(gate["id"]),
            level=str(gate["level"]),
            modules=[str(module) for module in gate.get("modules", [])],
            flow=str(gate["flow"]),
            max_hop_depth=int(gate["max_hop_depth"]),
            noise_profile=str(gate["noise_profile"]),
            required_evidence=[str(item) for item in gate.get("required_evidence", [])],
            expected_decision=str(gate["expected_decision"]),
        )
        for gate in gates
        if isinstance(gate, dict)
    ]


def validate_composite_level(
    level: str,
    gates: list[CompositeGate],
    *,
    threshold: dict[str, object],
    required_modules: set[str],
) -> CompositeGateResult:
    checked_gate_ids: list[str] = []
    max_hop_depth_value = threshold.get("max_hop_depth")
    required_gate_count_value = threshold.get("required_gate_count")
    if not isinstance(max_hop_depth_value, int) or not isinstance(required_gate_count_value, int):
        return CompositeGateResult(
            level=level,
            passed=False,
            checked_gate_ids=checked_gate_ids,
            max_hop_depth=0,
            reason=f"{level} threshold values must be integers",
        )
    max_hop_depth = max_hop_depth_value
    required_gate_count = required_gate_count_value

    if len(gates) != required_gate_count:
        return CompositeGateResult(
            level=level,
            passed=False,
            checked_gate_ids=checked_gate_ids,
            max_hop_depth=max_hop_depth,
            reason=f"{level} expected {required_gate_count} gates, got {len(gates)}",
        )

    for gate in gates:
        checked_gate_ids.append(gate.id)
        if gate.max_hop_depth > max_hop_depth:
            return CompositeGateResult(
                level=level,
                passed=False,
                checked_gate_ids=checked_gate_ids,
                max_hop_depth=max_hop_depth,
                reason=f"{gate.id} exceeds level hop depth",
            )
        if not gate.required_evidence:
            return CompositeGateResult(
                level=level,
                passed=False,
                checked_gate_ids=checked_gate_ids,
                max_hop_depth=max_hop_depth,
                reason=f"{gate.id} has no required evidence",
            )

    covered_modules = {module for gate in gates for module in gate.modules}
    if level == "extreme" and not required_modules.issubset(covered_modules):
        missing = sorted(required_modules - covered_modules)
        return CompositeGateResult(
            level=level,
            passed=False,
            checked_gate_ids=checked_gate_ids,
            max_hop_depth=max_hop_depth,
            reason=f"extreme gate missing modules: {missing}",
        )

    return CompositeGateResult(
        level=level,
        passed=True,
        checked_gate_ids=checked_gate_ids,
        max_hop_depth=max_hop_depth,
    )


def run_composite_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[CompositeGateResult]:
    data = load_yaml(config_path)
    order = data.get("promotion_order", [])
    thresholds = data.get("level_thresholds", {})
    required_modules = {str(module) for module in data.get("required_modules", [])}
    gates = load_composite_gates(config_path)

    results: list[CompositeGateResult] = []
    for level in order:
        if not isinstance(level, str):
            continue
        threshold = thresholds.get(level)
        if not isinstance(threshold, dict):
            continue
        level_gates = [gate for gate in gates if gate.level == level]
        result = validate_composite_level(
            level,
            level_gates,
            threshold=threshold,
            required_modules=required_modules,
        )
        results.append(result)
        if level == max_level:
            break
        if not result.passed:
            break
    return results
