from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class FlowMemoryRatingCase:
    id: str
    flow: list[str]
    scenario: str
    expected_decision: str
    hop_depth: int


@dataclass(frozen=True)
class FlowMemoryRatingLevel:
    name: str
    max_hop_depth: int
    cases: list[FlowMemoryRatingCase]
    required_to_promote: bool
    description: str


@dataclass(frozen=True)
class FlowMemoryRatingResult:
    level: str
    passed: bool
    checked_case_ids: list[str]
    max_hop_depth: int
    reason: str = ""


def parse_flow_memory_path(flow: str) -> list[str]:
    return [stage.strip() for stage in flow.split("->") if stage.strip()]


def infer_flow_memory_rating_decision(case: FlowMemoryRatingCase) -> str:
    decisions = {
        "role_bound_analogy": "select_flow_matched_memory",
        "negative_constraint": "preserve_constraint",
        "restore_state_after_branch": "restore_active_flow",
        "retracted_memory": "quarantine_memory",
        "bilingual_evidence": "pack_canonical_with_original_evidence",
        "wrong_flow_interference": "downrank_interference",
        "flow_score_dominates_similarity": "select_high_memory_score",
        "low_utility_token_cost": "prune_memory",
    }
    return decisions.get(case.scenario, "quarantine_memory")


def load_flow_memory_rating_levels(config_path: Path) -> list[FlowMemoryRatingLevel]:
    data = load_yaml(config_path)
    levels = data.get("flow_memory_rating_gate_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid flow memory rating config in {config_path}"
        raise ValueError(msg)

    loaded: list[FlowMemoryRatingLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        max_hop_depth = int(definition["max_hop_depth"])
        cases = [
            FlowMemoryRatingCase(
                id=str(case["id"]),
                flow=parse_flow_memory_path(str(case["flow"])),
                scenario=str(case["scenario"]),
                expected_decision=str(case["expected_decision"]),
                hop_depth=int(case.get("hop_depth", max_hop_depth)),
            )
            for case in definition.get("cases", [])
            if isinstance(case, dict)
        ]
        loaded.append(
            FlowMemoryRatingLevel(
                name=level_name,
                max_hop_depth=max_hop_depth,
                cases=cases,
                required_to_promote=bool(definition.get("required_to_promote", True)),
                description=str(definition.get("description", "")),
            )
        )
    return loaded


def run_flow_memory_rating_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[FlowMemoryRatingResult]:
    data = load_yaml(config_path)
    known_modules = set(data.get("flow_memory_modules", []))
    results: list[FlowMemoryRatingResult] = []
    for level in load_flow_memory_rating_levels(config_path):
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
                reason = f"{case.id} has unknown flow memory modules: {unknown}"
                break
            actual = infer_flow_memory_rating_decision(case)
            if actual != case.expected_decision:
                passed = False
                reason = f"{case.id} expected {case.expected_decision}, got {actual}"
                break
        result = FlowMemoryRatingResult(level.name, passed, checked, level.max_hop_depth, reason)
        results.append(result)
        if level.name == max_level:
            break
        if level.required_to_promote and not passed:
            break
    return results
