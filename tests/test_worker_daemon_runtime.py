from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from ai_local.cli import app


def _init_workspace(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "--workspace", str(tmp_path)])
    assert result.exit_code == 0, result.output


def test_daemon_run_once(tmp_path: Path) -> None:
    """Phase 4A: daemon run --once still works."""
    runner = CliRunner()
    _init_workspace(runner, tmp_path)

    result = runner.invoke(app, ["daemon", "run", "--workspace", str(tmp_path), "--once"])
    assert result.exit_code == 0, result.output
    assert "DAEMON run mode=once" in result.output
    assert "WORKER once" in result.output
    assert "LOG" in result.output


def test_daemon_run_loop_max_iterations_2(tmp_path: Path) -> None:
    """Daemon loop with --max-iterations 2 exits successfully."""
    runner = CliRunner()
    _init_workspace(runner, tmp_path)

    result = runner.invoke(
        app,
        [
            "daemon", "run",
            "--workspace", str(tmp_path),
            "--loop",
            "--poll-interval", "0.01",
            "--max-iterations", "2",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "DAEMON run mode=loop" in result.output
    assert "iteration=1" in result.output
    assert "iteration=2" in result.output
    assert "LOG" in result.output


def test_daemon_loop_prints_iteration_lines(tmp_path: Path) -> None:
    """Daemon loop prints WORKER loop iteration lines."""
    runner = CliRunner()
    _init_workspace(runner, tmp_path)

    result = runner.invoke(
        app,
        [
            "daemon", "run",
            "--workspace", str(tmp_path),
            "--loop",
            "--poll-interval", "0.01",
            "--max-iterations", "2",
        ],
    )
    assert result.exit_code == 0, result.output
    lines = result.output.strip().splitlines()
    worker_lines = [l for l in lines if l.startswith("WORKER loop")]
    assert len(worker_lines) == 2
    assert "iteration=1" in worker_lines[0]
    assert "iteration=2" in worker_lines[1]


def test_daemon_log_contains_jsonl_loop_entries(tmp_path: Path) -> None:
    """daemon.log contains JSONL loop entries."""
    runner = CliRunner()
    _init_workspace(runner, tmp_path)

    result = runner.invoke(
        app,
        [
            "daemon", "run",
            "--workspace", str(tmp_path),
            "--loop",
            "--poll-interval", "0.01",
            "--max-iterations", "2",
        ],
    )
    assert result.exit_code == 0, result.output

    log_path = tmp_path / ".ai-local" / "logs" / "daemon.log"
    assert log_path.exists()
    log_lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(log_lines) >= 2
    for line in log_lines:
        entry = json.loads(line)
        assert "timestamp" in entry
        assert "mode" in entry
        assert entry["mode"] == "loop"
        # An iteration loop entry has "iteration" (singular); a stop
        # event has "iterations" (plural).  Either is fine.
        assert "iteration" in entry or "iterations" in entry


def test_daemon_heartbeat_json_exists_and_stopped(tmp_path: Path) -> None:
    """daemon-heartbeat.json exists and ends with status stopped."""
    runner = CliRunner()
    _init_workspace(runner, tmp_path)

    result = runner.invoke(
        app,
        [
            "daemon", "run",
            "--workspace", str(tmp_path),
            "--loop",
            "--poll-interval", "0.01",
            "--max-iterations", "2",
        ],
    )
    assert result.exit_code == 0, result.output

    heartbeat_path = tmp_path / ".ai-local" / "reports" / "daemon-heartbeat.json"
    assert heartbeat_path.exists()
    hb = json.loads(heartbeat_path.read_text(encoding="utf-8"))
    assert hb["status"] == "stopped"
    assert hb["stop_reason"] == "max_iterations"
    assert hb["iterations"] == 2
    assert "pid" in hb
    assert "started_at" in hb
    assert "last_seen_at" in hb


def test_daemon_runtime_snapshot_includes_heartbeat(tmp_path: Path) -> None:
    """Runtime snapshot includes daemon heartbeat fields after daemon run."""
    runner = CliRunner()
    _init_workspace(runner, tmp_path)

    # Run daemon loop first
    result = runner.invoke(
        app,
        [
            "daemon", "run",
            "--workspace", str(tmp_path),
            "--loop",
            "--poll-interval", "0.01",
            "--max-iterations", "1",
        ],
    )
    assert result.exit_code == 0, result.output

    # Check runtime status includes daemon fields
    status_result = runner.invoke(
        app,
        ["runtime", "status", "--workspace", str(tmp_path)],
    )
    assert status_result.exit_code == 0, status_result.output
    assert "DAEMON status=stopped" in status_result.output

    # Check runtime snapshot includes daemon fields
    snapshot_result = runner.invoke(
        app,
        ["runtime", "snapshot", "--workspace", str(tmp_path)],
    )
    assert snapshot_result.exit_code == 0, snapshot_result.output
    assert "DAEMON status=stopped" in snapshot_result.output


def test_daemon_lock_blocks_running(tmp_path: Path) -> None:
    """Running heartbeat blocks daemon start."""
    runner = CliRunner()
    _init_workspace(runner, tmp_path)

    # Manually create a lock file with running heartbeat
    heartbeat_path = tmp_path / ".ai-local" / "reports" / "daemon-heartbeat.json"
    lock_path = tmp_path / ".ai-local" / "reports" / "daemon.lock"
    hb = {
        "status": "running",
        "mode": "loop",
        "pid": 99999,
        "started_at": "2025-01-01T00:00:00Z",
        "last_seen_at": "2025-01-01T00:00:00Z",
    }
    heartbeat_path.write_text(json.dumps(hb), encoding="utf-8")
    lock_path.touch()

    result = runner.invoke(
        app,
        [
            "daemon", "run",
            "--workspace", str(tmp_path),
            "--loop",
            "--poll-interval", "0.01",
            "--max-iterations", "1",
        ],
    )
    assert result.exit_code == 1, result.output
    assert "Daemon already running" in result.output


def test_daemon_force_bypasses_stale_lock(tmp_path: Path) -> None:
    """--force bypasses stale/running lock for MVP test."""
    runner = CliRunner()
    _init_workspace(runner, tmp_path)

    # Manually create a lock file with running heartbeat
    heartbeat_path = tmp_path / ".ai-local" / "reports" / "daemon-heartbeat.json"
    lock_path = tmp_path / ".ai-local" / "reports" / "daemon.lock"
    hb = {
        "status": "running",
        "mode": "loop",
        "pid": 99999,
        "started_at": "2025-01-01T00:00:00Z",
        "last_seen_at": "2025-01-01T00:00:00Z",
    }
    heartbeat_path.write_text(json.dumps(hb), encoding="utf-8")
    lock_path.touch()

    result = runner.invoke(
        app,
        [
            "daemon", "run",
            "--workspace", str(tmp_path),
            "--loop",
            "--force",
            "--poll-interval", "0.01",
            "--max-iterations", "1",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "DAEMON run mode=loop" in result.output


def test_daemon_lock_cleaned_up_after_run(tmp_path: Path) -> None:
    """Lock file is cleaned up after daemon run completes."""
    runner = CliRunner()
    _init_workspace(runner, tmp_path)

    result = runner.invoke(
        app,
        [
            "daemon", "run",
            "--workspace", str(tmp_path),
            "--loop",
            "--poll-interval", "0.01",
            "--max-iterations", "1",
        ],
    )
    assert result.exit_code == 0, result.output

    lock_path = tmp_path / ".ai-local" / "reports" / "daemon.lock"
    assert not lock_path.exists()


def test_daemon_once_with_job(tmp_path: Path) -> None:
    """Daemon --once processes a submitted job."""
    runner = CliRunner()
    _init_workspace(runner, tmp_path)

    # Submit a task first
    submit_result = runner.invoke(
        app,
        ["task", "submit", "Loop task", "--workspace", str(tmp_path)],
    )
    assert submit_result.exit_code == 0, submit_result.output

    # Run daemon once
    result = runner.invoke(
        app,
        ["daemon", "run", "--workspace", str(tmp_path), "--once"],
    )
    assert result.exit_code == 0, result.output
    assert "DAEMON run mode=once" in result.output
    assert "WORKER once PASS" in result.output
    assert "processed=1" in result.output


def test_daemon_loop_processes_job_then_skips(tmp_path: Path) -> None:
    """Daemon loop processes one job then skips when queue is empty."""
    runner = CliRunner()
    _init_workspace(runner, tmp_path)

    # Submit a task
    submit_result = runner.invoke(
        app,
        ["task", "submit", "Loop task", "--workspace", str(tmp_path)],
    )
    assert submit_result.exit_code == 0, submit_result.output

    # Run daemon loop with max 2 iterations
    result = runner.invoke(
        app,
        [
            "daemon", "run",
            "--workspace", str(tmp_path),
            "--loop",
            "--poll-interval", "0.01",
            "--max-iterations", "2",
        ],
    )
    assert result.exit_code == 0, result.output
    # First iteration should process the job
    assert "status=pass" in result.output
    # Second iteration should skip
    assert "status=skipped" in result.output
