from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

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
