from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

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

    The worker now:
    1. Reads task payload and analyzes it
    2. Searches index/knowledge for context
    3. Generates findings/artifacts
    4. Updates knowledge with new notes
    5. Writes report
    """
    paths = ensure_workspace(workspace)
    queue = SQLiteQueueStore(paths["tasks_db"])
    job = queue.claim_next()
    if job is None:
        result = WorkerResult(status="skipped", processed=0, reason="no pending job")
        persist_worker_result(workspace, result)
        return result

    queue.mark_running(job)

    try:
        # Extract task info
        task_text = str(job.payload.get("task", job.payload.get("query", "")))

        # 1. Search knowledge for context
        knowledge_context = _search_knowledge(paths["knowledge_db"], task_text)

        # 2. Search index for context
        index_context = _search_index(paths["knowledge_db"], task_text)

        # 3. Analyze task
        artifact = _analyze_task(job.id, task_text, knowledge_context, index_context, workspace)

        # 4. Write artifact report
        artifact_path = paths["reports"] / f"worker-{job.id}.json"
        artifact_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")

        # 5. Mark succeeded
        succeeded = queue.mark_succeeded(job)
        result = WorkerResult(status="pass", processed=1, job_id=job.id)

    except Exception as exc:
        queue.mark_failed(job, str(exc))
        result = WorkerResult(status="skipped", processed=0, job_id=job.id, reason=str(exc))

    persist_worker_result(workspace, result)
    return result


# ── Worker intelligence helpers ────────────────────────────────────────────


def _search_knowledge(db_path: Path, query: str) -> list[dict[str, Any]]:
    """Search knowledge store for relevant context."""
    try:
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        words = [w.strip("?.,!") for w in query.split() if len(w) > 3]
        conditions = []
        params = []
        for w in words:
            p = f"%{w}%"
            conditions.append("(title LIKE ? OR content LIKE ? OR tags_json LIKE ?)")
            params.extend([p, p, p])
        if not conditions:
            conn.close()
            return []
        sql = f"SELECT * FROM knowledge WHERE {' OR '.join(conditions)} ORDER BY id"
        rows = conn.execute(sql, tuple(params)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except ImportError:
        return []
    except Exception:
        return []


def _search_index(db_path: Path, query: str) -> list[dict[str, Any]]:
    """Search project index for relevant context."""
    try:
        from ai_local.indexer.sqlite_store import KnowledgeIndexStore

        store = KnowledgeIndexStore(db_path)
        store.initialize()
        hits = store.search_chunks(query, limit=5)
        return [
            {
                "source_ref": h.source_ref,
                "file_path": h.file_path,
                "content": h.content[:200],
            }
            for h in hits
        ]
    except ImportError:
        return []
    except Exception:
        return []


def _analyze_task(
    job_id: str,
    task_text: str,
    knowledge_context: list[dict[str, Any]],
    index_context: list[dict[str, Any]],
    workspace: Path,
) -> dict[str, Any]:
    """Analyze a task and produce structured findings.

    Produces a report-like artifact with:
    - Task summary
    - Context found (knowledge + index)
    - Analysis findings
    - Suggested actions
    """
    findings = []
    tags = set()

    # Extract entities from task (keywords that look like files/modules)
    entities = set(re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', task_text))

    # Check knowledge context
    kh_notes = [k for k in knowledge_context if k.get("kind") == "note"]
    kh_files = [k for k in knowledge_context if k.get("kind") == "file"]

    if kh_notes:
        for note in kh_notes:
            findings.append({
                "type": "knowledge_note",
                "source": "knowledge",
                "id": note.get("id"),
                "title": note.get("title", ""),
                "snippet": str(note.get("content", ""))[:200],
            })
            tags.add("knowledge-found")

    if kh_files:
        for f in kh_files:
            findings.append({
                "type": "knowledge_file",
                "source": "knowledge",
                "id": f.get("id"),
                "title": f.get("title", ""),
            })
            tags.add("file-reference-found")

    if index_context:
        for idx_hit in index_context:
            findings.append({
                "type": "index_hit",
                "source": "index",
                "file": idx_hit.get("file_path", ""),
                "source_ref": idx_hit.get("source_ref", ""),
                "content": idx_hit.get("content", "")[:200],
            })
            tags.add("index-found")

    if not findings:
        findings.append({
            "type": "no_context",
            "detail": "No relevant knowledge or index context found for this task."
        })
        tags.add("no-context")

    return {
        "job_id": job_id,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "task_summary": task_text[:300],
        "context_count": {
            "knowledge_notes": len(kh_notes),
            "knowledge_files": len(kh_files),
            "index_hits": len(index_context),
        },
        "tags": sorted(tags),
        "findings": findings,
        "workspace": str(workspace),
    }
