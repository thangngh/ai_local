from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml


@dataclass(frozen=True)
class PatchPipelineCase:
    id: str
    flow: list[str]
    expected_decision: str
    noise_type: str
    hop_depth: int


@dataclass(frozen=True)
class PatchPipelineLevel:
    name: str
    max_hop_depth: int
    cases: list[PatchPipelineCase]


@dataclass(frozen=True)
class PatchPipelineResult:
    level: str
    passed: bool
    checked_case_ids: list[str]
    max_hop_depth: int
    reason: str = ""


def parse_pipeline_flow(flow: str) -> list[str]:
    return [stage.strip() for stage in flow.split("->") if stage.strip()]


def infer_patch_pipeline_decision(case: PatchPipelineCase) -> str:
    if case.noise_type in {"weak_context"}:
        return "retrieve_more"
    if case.noise_type == "oversized_patch":
        return "split"
    if case.noise_type in {"bad_patch", "fixable_test_failure"}:
        return "retry"
    if case.noise_type == "risky_patch":
        return "ask_user"
    if case.noise_type in {"serious_test_failure", "deep_prompt_laundering"}:
        return "rollback"
    if case.noise_type == "more_patch_required":
        return "next_patch"
    return "accept"


def load_patch_pipeline_levels(config_path: Path) -> list[PatchPipelineLevel]:
    data = load_yaml(config_path)
    pipeline = data.get("patch_pipeline", {})
    order = data.get("promotion_order", [])
    if not isinstance(pipeline, dict) or not isinstance(order, list):
        msg = f"Invalid patch pipeline config in {config_path}"
        raise ValueError(msg)
    levels = pipeline.get("levels", {})
    if not isinstance(levels, dict):
        return []

    loaded: list[PatchPipelineLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        max_hop_depth = int(definition["max_hop_depth"])
        cases = [
            PatchPipelineCase(
                id=str(case["id"]),
                flow=parse_pipeline_flow(str(case["flow"])),
                expected_decision=str(case["expected_decision"]),
                noise_type=str(case["noise_type"]),
                hop_depth=int(case.get("hop_depth", max_hop_depth)),
            )
            for case in definition.get("cases", [])
            if isinstance(case, dict)
        ]
        loaded.append(PatchPipelineLevel(str(level_name), max_hop_depth, cases))
    return loaded


def validate_patch_pipeline_level(
    level: PatchPipelineLevel,
    *,
    known_stages: set[str],
) -> PatchPipelineResult:
    checked_case_ids: list[str] = []
    for case in level.cases:
        checked_case_ids.append(case.id)
        if case.hop_depth > level.max_hop_depth:
            return PatchPipelineResult(
                level.name,
                False,
                checked_case_ids,
                level.max_hop_depth,
                f"{case.id} exceeds max hop depth",
            )
        unknown = [stage for stage in case.flow if stage not in known_stages]
        if unknown:
            return PatchPipelineResult(
                level.name,
                False,
                checked_case_ids,
                level.max_hop_depth,
                f"{case.id} has unknown stages: {unknown}",
            )
        actual = infer_patch_pipeline_decision(case)
        if actual != case.expected_decision:
            return PatchPipelineResult(
                level.name,
                False,
                checked_case_ids,
                level.max_hop_depth,
                f"{case.id} expected {case.expected_decision}, got {actual}",
            )
    return PatchPipelineResult(level.name, True, checked_case_ids, level.max_hop_depth)


def run_patch_pipeline_promotion(
    *,
    config_path: Path,
    max_level: str | None = None,
) -> list[PatchPipelineResult]:
    data = load_yaml(config_path)
    pipeline = data.get("patch_pipeline", {})
    if not isinstance(pipeline, dict):
        msg = f"Invalid patch pipeline config in {config_path}"
        raise ValueError(msg)
    known_stages = {str(stage) for stage in pipeline.get("required_stages", [])}
    known_stages.update(
        {
            "RETRIEVE_MORE",
            "SPLIT_PATCH",
            "RETRY_PATCH",
            "ASK_USER",
            "ROLLBACK",
            "NEXT_PATCH",
        }
    )

    results: list[PatchPipelineResult] = []
    for level in load_patch_pipeline_levels(config_path):
        result = validate_patch_pipeline_level(level, known_stages=known_stages)
        results.append(result)
        if level.name == max_level:
            break
        if not result.passed:
            break
    return results

