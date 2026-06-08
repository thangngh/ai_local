from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from pathlib import Path
import json

from ai_local.queue.store import SQLiteQueueStore


@dataclass(frozen=True, slots=True)
class WorkerResult:
    """Result of a single worker execution.

    Attributes
    ----------
    status: Literal["pass", "skipped"]
        Whether the worker processed a job.
    processed: int
        Number of jobs processed (0 or 1 for now).
    job_id: str | None
        The ID of the job that was processed, if any.
    reason: str | None
        Reason for skipping when no job was available.
    """

    status: Literal["pass", "skipped"]
    processed: int
    job_id: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict:
        """Serialize the result to a JSON‑compatible dict."""
        data: dict = {"status": self.status, "processed": self.processed}
        if self.job_id is not None:
            data["job_id"] = self.job_id
        if self.reason is not None:
            data["reason"] = self.reason
        return data


def ensure_workspace(workspace: Path) -> dict[str, Path]:
    """Create the ``.ai-local`` directory structure if missing.

    Returns the same mapping used throughout the project.
    """
    base = workspace / ".ai-local"
    dirs = {
        "base": base,
        "logs": base / "logs",
        "reports": base / "reports",
        "backups": base / "backups",
    }
    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)
    return {
        **dirs,
        "config": base / "config.yaml",
        "knowledge_db": base / "knowledge.db",
        "runtime_db": base / "runtime.db",
        "tasks_db": base / "tasks.db",
        "audit_db": base / "audit.db",
    }


def persist_worker_result(workspace: Path, result: WorkerResult) -> None:
    """Write the ``WorkerResult`` as a single JSON object to ``reports/last-worker-result.json``.
    The file is overwritten each time.
    """
    paths = ensure_workspace(workspace)
    report_path = paths["reports"] / "last-worker-result.json"
    # Overwrite with a single JSON object as required
    report_path.write_text(json.dumps(result.to_dict(), separators=(",", ":")), encoding="utf-8")


def load_last_worker_result(workspace: Path) -> dict | None:
    """Load the worker result from ``last-worker-result.json`` (single JSON object).
    Returns ``None`` if the file does not exist or cannot be parsed.
    """
    paths = ensure_workspace(workspace)
    report_path = paths["reports"] / "last-worker-result.json"
    if not report_path.exists():
        return None
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def run_worker_once(workspace: Path) -> WorkerResult:
    """Process a single job (or none) according to the contract.
    Persists the result and returns it.
    """
    paths = ensure_workspace(workspace)
    queue = SQLiteQueueStore(paths["tasks_db"])
    job = queue.claim_next()
    if job is None:
        result = WorkerResult(status="skipped", processed=0, reason="no pending job")
    else:
        queue.mark_running(job)
        queue.mark_succeeded(job)
        result = WorkerResult(status="pass", processed=1, job_id=job.id)
    persist_worker_result(workspace, result)
    return result
