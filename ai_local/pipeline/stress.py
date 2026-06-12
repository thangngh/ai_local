from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ai_local.audit.store import InMemoryAuditStore
from ai_local.config.loader import load_yaml
from ai_local.indexer.project import refresh_and_retrieve_project
from ai_local.indexer.sqlite_store import KnowledgeIndexStore
from ai_local.queue.models import Job, JobStatus
from ai_local.queue.store import InMemoryQueueStore
from ai_local.queue.worker import QueueWorker


StressKind = Literal["retriever", "queue", "worker_timeout"]


@dataclass(frozen=True)
class Phase9StressCase:
    id: str
    kind: StressKind
    hop_depth: int
    params: dict[str, object]


@dataclass(frozen=True)
class Phase9StressResult:
    case_id: str
    kind: StressKind
    passed: bool
    hop_depth: int
    metrics: dict[str, int | str]
    reasons: list[str]


def load_phase9_stress_cases(config_path: Path) -> list[Phase9StressCase]:
    data = load_yaml(config_path)
    cases = data.get("stress_cases", [])
    if not isinstance(cases, list):
        msg = f"Invalid Phase 9 stress config in {config_path}"
        raise ValueError(msg)
    loaded: list[Phase9StressCase] = []
    for item in cases:
        if not isinstance(item, dict):
            continue
        kind = str(item["kind"])
        if kind not in {"retriever", "queue", "worker_timeout"}:
            msg = f"Unsupported Phase 9 stress kind: {kind}"
            raise ValueError(msg)
        params = {str(key): value for key, value in item.items() if key not in {"id", "kind"}}
        loaded.append(
            Phase9StressCase(
                id=str(item["id"]),
                kind=kind,  # type: ignore[arg-type]
                hop_depth=_int_value(item["hop_depth"]),
                params=params,
            )
        )
    return loaded


def run_phase9_stress_cases(
    *,
    config_path: Path,
    workspace_root: Path,
) -> list[Phase9StressResult]:
    workspace_root.mkdir(parents=True, exist_ok=True)
    return [
        run_phase9_stress_case(case, workspace_root=workspace_root / case.id)
        for case in load_phase9_stress_cases(config_path)
    ]


def run_phase9_stress_case(
    case: Phase9StressCase,
    *,
    workspace_root: Path,
) -> Phase9StressResult:
    workspace_root.mkdir(parents=True, exist_ok=True)
    if case.kind == "retriever":
        return _run_retriever_case(case, workspace_root)
    if case.kind == "queue":
        return _run_queue_case(case)
    return _run_worker_timeout_case(case)


def _run_retriever_case(case: Phase9StressCase, workspace_root: Path) -> Phase9StressResult:
    file_count = _param_int(case, "file_count")
    chunk_lines = _param_int(case, "chunk_lines")
    query = str(case.params["query"])
    for index in range(file_count):
        source = workspace_root / "docs" / f"stress-{index:03}.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            f"needle evidence document {index}\nnoise line {index}\n",
            encoding="utf-8",
        )

    store = KnowledgeIndexStore(workspace_root / "knowledge.db")
    first = refresh_and_retrieve_project(query, workspace_root, store, chunk_lines=chunk_lines, clear_store=True)
    second = refresh_and_retrieve_project(query, workspace_root, store, chunk_lines=chunk_lines)
    metrics: dict[str, int | str] = {
        "first_indexed": len(first.batch.documents),
        "second_unchanged": len(second.batch.unchanged_paths),
        "selected_hits": len(second.package.selected_hits),
        "decision": second.package.decision,
    }
    reasons = [
        reason
        for reason in [
            _expect_int(case, metrics, "first_indexed", "expected_first_indexed"),
            _expect_int(case, metrics, "second_unchanged", "expected_second_unchanged"),
            _expect_min_int(case, metrics, "selected_hits", "expected_min_hits"),
            _expect_value(case, metrics, "decision", "expected_decision"),
        ]
        if reason
    ]
    return Phase9StressResult(case.id, case.kind, not reasons, case.hop_depth, metrics, reasons)


def _run_queue_case(case: Phase9StressCase) -> Phase9StressResult:
    job_count = _param_int(case, "job_count")
    failing_jobs = _param_int(case, "failing_jobs")
    max_attempts = _param_int(case, "max_attempts")
    queue = InMemoryQueueStore()
    audit = InMemoryAuditStore()
    failing_ids = {f"job-{index:03}" for index in range(failing_jobs)}
    for index in range(job_count):
        queue.enqueue(
            Job(
                id=f"job-{index:03}",
                type="stress",
                priority=index,
                payload={},
                max_attempts=max_attempts,
            )
        )

    def handler(job: Job) -> None:
        if job.id in failing_ids:
            raise RuntimeError("stress failure")

    worker = QueueWorker(queue, handler, audit_store=audit)
    _drain_queue(worker, max_runs=job_count * max_attempts)
    metrics = _queue_metrics(queue, audit)
    reasons = [
        reason
        for reason in [
            _expect_int(case, metrics, "succeeded", "expected_succeeded"),
            _expect_int(case, metrics, "dead_letter", "expected_dead_letter"),
            _expect_int(case, metrics, "audit_events", "expected_audit_events"),
        ]
        if reason
    ]
    return Phase9StressResult(case.id, case.kind, not reasons, case.hop_depth, metrics, reasons)


def _run_worker_timeout_case(case: Phase9StressCase) -> Phase9StressResult:
    job_count = _param_int(case, "job_count")
    max_attempts = _param_int(case, "max_attempts")
    queue = InMemoryQueueStore()
    audit = InMemoryAuditStore()
    for index in range(job_count):
        queue.enqueue(
            Job(
                id=f"timeout-{index:03}",
                type="stress_timeout",
                priority=index,
                payload={"simulate_timeout": True},
                max_attempts=max_attempts,
            )
        )

    def handler(job: Job) -> None:
        if job.payload.get("simulate_timeout") is True:
            raise TimeoutError("worker handler timed out")

    worker = QueueWorker(queue, handler, audit_store=audit)
    _drain_queue(worker, max_runs=job_count * max_attempts)
    metrics = _queue_metrics(queue, audit)
    metrics["timeout_errors"] = sum(
        1 for job in queue._jobs if job.last_error == "worker handler timed out"  # noqa: SLF001
    )
    reasons = [
        reason
        for reason in [
            _expect_int(case, metrics, "dead_letter", "expected_dead_letter"),
            _expect_int(case, metrics, "timeout_errors", "expected_timeout_errors"),
            _expect_int(case, metrics, "audit_events", "expected_audit_events"),
        ]
        if reason
    ]
    return Phase9StressResult(case.id, case.kind, not reasons, case.hop_depth, metrics, reasons)


def _drain_queue(worker: QueueWorker, *, max_runs: int) -> None:
    for _ in range(max_runs):
        if worker.run_one() is None:
            return


def _queue_metrics(queue: InMemoryQueueStore, audit: InMemoryAuditStore) -> dict[str, int | str]:
    return {
        "succeeded": sum(1 for job in queue._jobs if job.status == JobStatus.SUCCEEDED),  # noqa: SLF001
        "dead_letter": sum(1 for job in queue._jobs if job.status == JobStatus.DEAD_LETTER),  # noqa: SLF001
        "pending": sum(1 for job in queue._jobs if job.status == JobStatus.PENDING),  # noqa: SLF001
        "audit_events": len(audit.list_events()),
    }


def _expect_int(
    case: Phase9StressCase,
    metrics: dict[str, int | str],
    metric_name: str,
    expected_name: str,
) -> str | None:
    expected = _param_int(case, expected_name)
    actual = metrics[metric_name]
    if actual != expected:
        return f"{case.id}: expected {metric_name}={expected}, got {actual}"
    return None


def _expect_min_int(
    case: Phase9StressCase,
    metrics: dict[str, int | str],
    metric_name: str,
    expected_name: str,
) -> str | None:
    expected = _param_int(case, expected_name)
    actual = metrics[metric_name]
    if not isinstance(actual, int) or actual < expected:
        return f"{case.id}: expected {metric_name}>={expected}, got {actual}"
    return None


def _expect_value(
    case: Phase9StressCase,
    metrics: dict[str, int | str],
    metric_name: str,
    expected_name: str,
) -> str | None:
    expected = str(case.params[expected_name])
    actual = metrics[metric_name]
    if actual != expected:
        return f"{case.id}: expected {metric_name}={expected}, got {actual}"
    return None


def _param_int(case: Phase9StressCase, name: str) -> int:
    return _int_value(case.params[name])


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    msg = f"Expected int-like value, got {type(value).__name__}"
    raise ValueError(msg)
