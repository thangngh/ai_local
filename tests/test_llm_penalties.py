from __future__ import annotations

import json
from pathlib import Path

from ai_local.benchmark.llm_penalties import (
    has_injection_related_failure,
    penalize_llm_scores,
)
from ai_local.benchmark.models import BenchmarkScores, GoldenTask
from ai_local.benchmark.rubric import compute_system_score


def test_penalize_safety_partial_cannot_have_perfect_llm_score() -> None:
    task = GoldenTask.model_validate(
        json.loads(Path("golden_tasks/block_env_exfiltration/task.json").read_text(encoding="utf-8"))
    )
    llm_scores = BenchmarkScores(
        task_success=1.0,
        evidence_score=1.0,
        retrieval_score=1.0,
        memory_score=1.0,
        safety_score=1.0,
        tool_score=1.0,
        patch_score=1.0,
        performance_score=1.0,
    )
    penalized = penalize_llm_scores(task, llm_scores, ["wrapper DATA_ONLY"])
    system = compute_system_score(penalized.as_dict())
    assert penalized.safety_score < 1.0
    assert system < 1.0
    assert has_injection_related_failure(["wrapper DATA_ONLY"])


def test_injection_failure_detected() -> None:
    assert has_injection_related_failure(["injection_score high quarantine"])
    assert not has_injection_related_failure(["small scope"])
