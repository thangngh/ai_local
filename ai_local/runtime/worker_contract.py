"""Worker contract — processes a single job with optional LLM enhancement.

The worker:
1. Claims a job from the queue
2. Searches knowledge + index for context
3. Analyzes the task (deterministic or LLM-based)
4. Optionally applies code changes via tool execution
5. Writes artifact report
6. Marks job succeeded/failed
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ai_local.llm.ollama import OllamaClient, OllamaError
from ai_local.queue.store import SQLiteQueueStore
from ai_local.tools.registry import ToolRegistry


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
        """Serialize the result to a JSON-compatible dict."""
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


def run_worker_once(
    workspace: Path,
    ollama_client: OllamaClient | None = None,
) -> WorkerResult:
    """Process a single job (or none) according to the contract.

    Args:
        workspace: The workspace directory.
        ollama_client: Optional Ollama client for LLM-enhanced analysis.

    The worker:
    1. Reads task payload and analyzes it
    2. Searches index/knowledge for context
    3. Generates findings/artifacts
    4. Optionally applies code changes (when LLM + tool registry available)
    5. Updates knowledge with new notes
    6. Writes report
    """
    paths = ensure_workspace(workspace)
    queue = SQLiteQueueStore(paths["tasks_db"])
    job = queue.claim_next()
    if job is None:
        result = WorkerResult(status="skipped", processed=0, reason="no pending job")
        persist_worker_result(workspace, result)
        return result

    job = queue.mark_running(job)

    try:
        # Extract task info
        task_text = str(job.payload.get("task", job.payload.get("query", "")))

        # 1. Search knowledge for context
        knowledge_context = _search_knowledge(paths["knowledge_db"], task_text)

        # 2. Search index for context
        index_context = _search_index(paths["knowledge_db"], task_text)

        # 3. Analyze task (deterministic or LLM-based)
        artifact = _analyze_task(
            job.id, task_text, knowledge_context, index_context,
            workspace, ollama_client=ollama_client,
        )

        # NOTE: Code changes are NOT applied automatically.
        # The LLM generates suggestions only — user reviews and decides.
        # See ai-local-control-principle.md (memory).
        if artifact.get("code_changes"):
            artifact["code_changes_note"] = (
                "These changes are suggestions for user review. "
                "They have NOT been applied."
            )

        artifact["execution_state"] = "proposal_ready"
        artifact["applied"] = False

        # 5. Write artifact report
        artifact_path = paths["reports"] / f"worker-{job.id}.json"
        artifact_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")

        # 6. Mark as a reviewable proposal. This is intentionally not
        # "succeeded"; no code edits or validation commands have run here.
        queue.mark_proposal_ready(job)
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
    ollama_client: OllamaClient | None = None,
) -> dict[str, Any]:
    """Analyze a task and produce structured findings.

    Uses LLM when available for deeper analysis, including code change
    suggestions (file path, original snippet, replacement snippet).

    Returns a report-like artifact with:
    - Task summary
    - Context found (knowledge + index)
    - Analysis findings
    - Suggested actions / code changes
    - Tool execution results
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
            "detail": "No relevant knowledge or index context found for this task.",
        })
        tags.add("no-context")

    # LLM-based code change generation
    code_changes: list[dict[str, Any]] | None = None
    llm_analysis: str | None = None
    llm_reasoning: str | None = None

    if ollama_client is not None:
        try:
            llm_result = _llm_analyze_task(
                ollama_client, task_text, kh_notes, index_context,
            )
            code_changes = llm_result.get("changes", [])
            llm_analysis = llm_result.get("analysis", "")
            llm_reasoning = llm_result.get("reasoning", "")
            if code_changes:
                tags.add("llm-changes-generated")
        except (OllamaError, json.JSONDecodeError) as exc:
            llm_reasoning = f"LLM analysis failed: {exc}"

    # Build artifact
    artifact: dict[str, Any] = {
        "job_id": job_id,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "task_summary": task_text[:300],
        "llm_used": ollama_client is not None,
        "context_count": {
            "knowledge_notes": len(kh_notes),
            "knowledge_files": len(kh_files),
            "index_hits": len(index_context),
        },
        "tags": sorted(tags),
        "findings": findings,
        "workspace": str(workspace),
    }

    if llm_analysis is not None:
        artifact["llm_analysis"] = llm_analysis
    if llm_reasoning is not None:
        artifact["llm_reasoning"] = llm_reasoning
    if code_changes is not None:
        artifact["code_changes"] = code_changes

    return artifact


def _llm_analyze_task(
    client: OllamaClient,
    task: str,
    knowledge_notes: list[dict[str, Any]],
    index_hits: list[dict[str, Any]],
) -> dict[str, Any]:
    """Use LLM to analyze a task and propose code changes.

    Expected return structure::
        {
            "analysis": "Summary of the task...",
            "reasoning": "Step-by-step reasoning...",
            "changes": [
                {
                    "file": "relative/path/to/file",
                    "description": "What to change",
                    "original_snippet": "code to replace",
                    "new_snippet": "replacement code"
                }
            ]
        }
    """
    system = (
        "You are a senior software engineer analyzing a coding task. "
        "Given the task description, relevant knowledge notes, and code context, "
        "provide a structured analysis. "
        "Return ONLY a JSON object with these keys: "
        '"analysis" (str), "reasoning" (str), "changes" (list of objects). '
        "Each change object must have: "
        '"file" (str), "description" (str), '
        '"original_snippet" (str), "new_snippet" (str). '
        "If no code changes are needed, return empty changes list. "
        "No markdown, no explanation outside JSON."
    )
    user = json.dumps({
        "task": task[:2000],
        "knowledge_notes": [
            {"title": n.get("title", "?"), "content": str(n.get("content", ""))[:300]}
            for n in knowledge_notes[:5]
        ],
        "code_context": [
            {"file": h.get("file_path", "?"), "content": h.get("content", "")[:300]}
            for h in index_hits[:5]
        ],
    })

    result = client.chat(system=system, user=user)
    raw = result.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]

    parsed: dict[str, Any] = json.loads(raw)
    if "changes" not in parsed:
        parsed["changes"] = []
    return parsed
