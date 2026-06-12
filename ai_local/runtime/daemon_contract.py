from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from ai_local.llm.ollama import OllamaClient
from ai_local.runtime.worker_contract import ensure_workspace


def load_daemon_heartbeat(workspace: Path) -> dict | None:
    """Load the daemon heartbeat JSON, or ``None`` if missing / corrupt."""
    paths = ensure_workspace(workspace)
    hb_path = paths["reports"] / "daemon-heartbeat.json"
    if not hb_path.exists():
        return None
    try:
        return json.loads(hb_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_daemon_heartbeat(
    workspace: Path,
    status: str,
    mode: str,
    iteration: int | None = None,
    stop_reason: str | None = None,
) -> dict:
    """Write the daemon heartbeat JSON.

    Preserves ``started_at`` from an existing heartbeat so the first
    timestamp survives across writes.
    """
    paths = ensure_workspace(workspace)
    hb_path = paths["reports"] / "daemon-heartbeat.json"
    now = datetime.now(timezone.utc).isoformat()

    existing = load_daemon_heartbeat(workspace) or {}

    hb: dict = {
        "status": status,
        "mode": mode,
        "pid": os.getpid(),
        "started_at": existing.get("started_at", now),
        "last_seen_at": now,
    }
    if iteration is not None:
        hb["iterations"] = iteration
    if stop_reason is not None:
        hb["stop_reason"] = stop_reason

    hb_path.write_text(json.dumps(hb, separators=(",", ":")), encoding="utf-8")
    return hb


def acquire_daemon_lock(workspace: Path) -> Path:
    """Create the daemon lock file and return its path."""
    paths = ensure_workspace(workspace)
    lock = paths["reports"] / "daemon.lock"
    lock.touch(exist_ok=True)
    return lock


def release_daemon_lock(workspace: Path) -> None:
    """Remove the daemon lock file (no-op if missing)."""
    paths = ensure_workspace(workspace)
    lock = paths["reports"] / "daemon.lock"
    lock.unlink(missing_ok=True)


def daemon_lock_ok(workspace: Path, force: bool = False) -> bool:
    """Check whether the daemon lock is safe to ignore.

    Returns ``True`` when it is safe to proceed (no lock, or stale, or
    ``--force`` was given).  Returns ``False`` when a running daemon
    lock is detected and the caller should abort.
    """
    paths = ensure_workspace(workspace)
    lock = paths["reports"] / "daemon.lock"
    if not lock.exists():
        return True
    hb = load_daemon_heartbeat(workspace)
    if hb and hb.get("status") == "running" and not force:
        return False
    # Stale lock — clean up
    release_daemon_lock(workspace)
    return True


def append_daemon_log(workspace: Path, entry: dict) -> None:
    """Append a JSON line to ``daemon.log``."""
    paths = ensure_workspace(workspace)
    log_path = paths["logs"] / "daemon.log"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")
        f.flush()


def daemon_timestamp() -> str:
    """Return a UTC ISO-8601 timestamp string."""
    return datetime.now(timezone.utc).isoformat()


def run_daemon_loop(
    *,
    workspace: Path,
    poll_interval: float,
    max_iterations: int | None = None,
    should_stop: Callable[[], bool] | None = None,
    emit_line: Callable[[str], None] | None = None,
    ollama_client: OllamaClient | None = None,
) -> int:
    """Run the daemon loop, processing jobs until a stop condition is met.

    Parameters
    ----------
    workspace:
        The workspace directory (resolved to absolute inside).
    poll_interval:
        Seconds to sleep between iterations.
    max_iterations:
        If set, stop after this many iterations.
    should_stop:
        Optional callback; the loop exits when this returns ``True``.
        Checked *before* each iteration and after sleeping.
    emit_line:
        Optional callback for human-readable output lines (e.g. CLI
        printing).  If ``None``, no output is emitted.

    Returns
    -------
    The number of iterations completed.

    Notes
    -----
    - Acquires and releases the daemon lock.
    - Writes heartbeat after each iteration.
    - Appends JSONL log entries for each iteration and stop event.
    - Handles ``max_iterations`` and ``should_stop`` cleanly.
    """
    from ai_local.runtime.worker_contract import run_worker_once

    mode = "loop"
    if emit_line:
        emit_line(
            f"DAEMON run mode=loop poll_interval={poll_interval} "
            f"max_iterations={max_iterations}"
        )

    acquire_daemon_lock(workspace)
    write_daemon_heartbeat(workspace, status="running", mode=mode)

    iteration = 0
    try:
        while True:
            if should_stop is not None and should_stop():
                break

            iteration += 1
            result = run_worker_once(workspace, ollama_client=ollama_client)

            # Console output
            if emit_line:
                if result.status == "pass":
                    emit_line(
                        f"WORKER loop iteration={iteration} status=pass "
                        f"processed={result.processed} job_id={result.job_id}"
                    )
                else:
                    emit_line(
                        f"WORKER loop iteration={iteration} status=skipped "
                        f'processed={result.processed} reason="{result.reason}"'
                    )

            # JSONL log entry
            append_daemon_log(
                workspace,
                {
                    "timestamp": daemon_timestamp(),
                    "component": "daemon",
                    "mode": "loop",
                    "iteration": iteration,
                    "worker": {
                        "status": result.status,
                        "processed": result.processed,
                        "job_id": result.job_id,
                        "reason": result.reason,
                    },
                },
            )
            write_daemon_heartbeat(
                workspace, status="running", mode=mode, iteration=iteration
            )

            if max_iterations is not None and iteration >= max_iterations:
                break

            if should_stop is not None and should_stop():
                break

            time.sleep(poll_interval)

            if should_stop is not None and should_stop():
                break

    except KeyboardInterrupt:
        write_daemon_heartbeat(
            workspace,
            status="stopped",
            mode=mode,
            iteration=iteration,
            stop_reason="keyboard_interrupt",
        )
        append_daemon_log(
            workspace,
            {
                "timestamp": daemon_timestamp(),
                "component": "daemon",
                "event": "stopped",
                "mode": "loop",
                "stop_reason": "keyboard_interrupt",
                "iterations": iteration,
            },
        )
        raise

    else:
        stop_reason = "max_iterations"
        if should_stop is not None and should_stop():
            stop_reason = "should_stop"
        write_daemon_heartbeat(
            workspace,
            status="stopped",
            mode=mode,
            iteration=iteration,
            stop_reason=stop_reason,
        )
        append_daemon_log(
            workspace,
            {
                "timestamp": daemon_timestamp(),
                "component": "daemon",
                "event": "stopped",
                "mode": "loop",
                "stop_reason": stop_reason,
                "iterations": iteration,
            },
        )
    finally:
        release_daemon_lock(workspace)

    return iteration
