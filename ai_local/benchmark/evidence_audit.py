from __future__ import annotations

from dataclasses import dataclass

from ai_local.benchmark.models import BenchmarkRunReport, BenchmarkTaskResult


@dataclass(frozen=True)
class EvidenceGap:
    task_id: str
    category: str
    missing_refs: list[str]
    evidence_score: float
    result: str


def _missing_refs_for_task(task: BenchmarkTaskResult) -> list[str]:
    trace = task.debug_trace
    explicit = trace.get("missing_required_evidence")
    if isinstance(explicit, list):
        return [str(item) for item in explicit]
    required = trace.get("required_evidence")
    if not isinstance(required, list):
        return []
    retrieved = set(task.retrieved_refs)
    return [ref for ref in required if ref not in retrieved]


def audit_evidence_gaps(report: BenchmarkRunReport) -> list[EvidenceGap]:
    from ai_local.benchmark.metrics import _task_has_evidence_gap

    gaps: list[EvidenceGap] = []
    for task in report.tasks:
        if not _task_has_evidence_gap(task):
            continue
        missing = _missing_refs_for_task(task)
        gaps.append(
            EvidenceGap(
                task_id=task.task_id,
                category=task.category,
                missing_refs=missing,
                evidence_score=task.scores.evidence_score,
                result=task.result,
            )
        )
    return gaps


def missing_evidence_rate(report: BenchmarkRunReport) -> float:
    if not report.tasks:
        return 0.0
    gaps = audit_evidence_gaps(report)
    return round(len(gaps) / len(report.tasks), 4)


def safety_knowledge_evidence_gaps(report: BenchmarkRunReport) -> list[EvidenceGap]:
    return [
        gap
        for gap in audit_evidence_gaps(report)
        if gap.category in {"safety", "knowledge"}
    ]
