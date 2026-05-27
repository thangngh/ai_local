from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

BenchmarkResultLabel = Literal["pass", "partial", "fail"]


class GoldenTask(BaseModel):
    task_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    input: str = ""
    expected_behavior: str = ""
    required_evidence: list[str] = Field(default_factory=list)
    forbidden_behavior: list[str] = Field(default_factory=list)
    pass_criteria: list[str] = Field(default_factory=list)
    evaluator: str = Field(min_length=1)
    evaluator_payload: dict[str, Any] = Field(default_factory=dict)
    graded_dimensions: list[str] = Field(default_factory=list)
    performance_budget_ms: int | None = Field(default=None, ge=1)


class BenchmarkScores(BaseModel):
    task_success: float = 0.0
    evidence_score: float = 0.0
    retrieval_score: float = 0.0
    memory_score: float = 0.0
    safety_score: float = 0.0
    tool_score: float = 0.0
    patch_score: float = 0.0
    performance_score: float = 1.0

    def as_dict(self) -> dict[str, float]:
        return {
            "task_success": self.task_success,
            "evidence_score": self.evidence_score,
            "retrieval_score": self.retrieval_score,
            "memory_score": self.memory_score,
            "safety_score": self.safety_score,
            "tool_score": self.tool_score,
            "patch_score": self.patch_score,
            "performance_score": self.performance_score,
        }


class TaskTokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    input_chars: int = 0
    output_chars: int = 0
    latency_ms: int = 0
    tokens_per_second: float = 0.0
    estimated_cost_usd: float = 0.0
    token_source: str = "unknown"
    eval_duration_ns: int | None = None


class BenchmarkCostAggregate(BaseModel):
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_latency_ms: int = 0
    estimated_cost_usd: float = 0.0
    output_tokens_per_second: float = 0.0
    avg_input_tokens_per_task: float = 0.0
    avg_output_tokens_per_task: float = 0.0
    avg_cost_usd_per_task: float = 0.0


class BenchmarkTaskResult(BaseModel):
    benchmark_id: str
    run_id: str
    task_id: str
    category: str
    result: BenchmarkResultLabel
    harness_scores: BenchmarkScores
    llm_scores: BenchmarkScores | None = None
    scores: BenchmarkScores
    system_score: float
    harness_system_score: float
    llm_system_score: float | None = None
    failures: list[str] = Field(default_factory=list)
    retrieved_refs: list[str] = Field(default_factory=list)
    used_memories: list[str] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)
    gate_decisions: list[str] = Field(default_factory=list)
    latency_ms: int | None = None
    token_usage: TaskTokenUsage | None = None
    debug_trace: dict[str, Any] = Field(default_factory=dict)


class MemoryBenchmarkMetrics(BaseModel):
    precision_at_5: float = 0.0
    stale_memory_used_rate: float = 0.0
    conflict_memory_used_rate: float = 0.0
    active_memory_with_evidence: float = 0.0
    user_correction_rate: float = 0.0
    safety_violation_count: int = 0


class RetrievalBenchmarkMetrics(BaseModel):
    precision_at_k: float = 0.0
    recall_at_k: float = 0.0
    mrr: float = 0.0
    context_noise_rate: float = 0.0
    missing_evidence_rate: float = 0.0


class PatchBenchmarkMetrics(BaseModel):
    patch_apply_success: float = 0.0
    test_pass_rate: float = 0.0
    rollback_success: float = 0.0
    max_files_changed_violation: float = 0.0
    unrelated_diff_rate: float = 0.0


class BenchmarkAggregate(BaseModel):
    system_score: float
    harness_system_score: float = 0.0
    llm_system_score: float | None = None
    tier: str
    pass_count: int
    partial_count: int
    fail_count: int
    total: int
    personal_targets_met: dict[str, bool]
    memory_metrics: MemoryBenchmarkMetrics
    retrieval_metrics: RetrievalBenchmarkMetrics
    patch_metrics: PatchBenchmarkMetrics


class BenchmarkRunReport(BaseModel):
    benchmark_id: str
    run_id: str
    generated_at: str
    run_mode: str = "harness"
    ollama_model: str | None = None
    ollama_base_url: str | None = None
    harness_weight: float | None = None
    cost: BenchmarkCostAggregate = Field(default_factory=BenchmarkCostAggregate)
    tasks: list[BenchmarkTaskResult]
    aggregate: BenchmarkAggregate
