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
    worker_lines = [ln for ln in lines if ln.startswith("WORKER loop")]
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


# ── Phase 4C — Runtime logs, stale detection, service dry-run, demo daemon ──


def test_runtime_logs_missing(tmp_path: Path) -> None:
    """runtime logs with missing log prints LOGS none."""
    runner = CliRunner()
    _init_workspace(runner, tmp_path)

    result = runner.invoke(
        app,
        ["runtime", "logs", "--workspace", str(tmp_path), "--tail", "5"],
    )
    assert result.exit_code == 0, result.output
    assert "LOGS none" in result.output


def test_runtime_logs_tail(tmp_path: Path) -> None:
    """runtime logs --tail 2 prints only last 2 JSONL lines after daemon loop."""
    runner = CliRunner()
    _init_workspace(runner, tmp_path)

    # Run daemon loop with 3 iterations so we have ≥3 log lines
    runner.invoke(
        app,
        [
            "daemon", "run",
            "--workspace", str(tmp_path),
            "--loop",
            "--poll-interval", "0.01",
            "--max-iterations", "3",
        ],
    )

    log_path = tmp_path / ".ai-local" / "logs" / "daemon.log"
    assert log_path.exists()
    full_lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(full_lines) >= 3

    result = runner.invoke(
        app,
        ["runtime", "logs", "--workspace", str(tmp_path), "--tail", "2"],
    )
    assert result.exit_code == 0, result.output
    lines = result.output.strip().splitlines()
    assert len(lines) == 3  # header line + 2 log lines
    assert "tail=2" in lines[0]


def test_runtime_snapshot_includes_stale_fields(tmp_path: Path) -> None:
    """Runtime snapshot includes daemon_stale and daemon_stale_after_seconds."""
    runner = CliRunner()
    _init_workspace(runner, tmp_path)

    runner.invoke(
        app,
        [
            "daemon", "run",
            "--workspace", str(tmp_path),
            "--loop",
            "--poll-interval", "0.01",
            "--max-iterations", "1",
        ],
    )

    result = runner.invoke(
        app,
        ["runtime", "snapshot", "--workspace", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output

    snapshot_path = tmp_path / ".ai-local" / "reports" / "runtime-snapshot.json"
    assert snapshot_path.exists()
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert "daemon_stale_after_seconds" in data
    assert data["daemon_stale_after_seconds"] == 60


def test_synthetic_stale_heartbeat_detected(tmp_path: Path) -> None:
    """Synthetic stale heartbeat is detected as daemon_stale=true."""
    runner = CliRunner()
    _init_workspace(runner, tmp_path)

    # Write a heartbeat with status=running but last_seen_at far in the past
    heartbeat_path = tmp_path / ".ai-local" / "reports" / "daemon-heartbeat.json"
    hb = {
        "status": "running",
        "mode": "loop",
        "pid": 99999,
        "started_at": "2025-01-01T00:00:00Z",
        "last_seen_at": "2025-01-01T00:00:00Z",
        "iterations": 5,
    }
    heartbeat_path.write_text(json.dumps(hb), encoding="utf-8")

    result = runner.invoke(
        app,
        ["runtime", "status", "--workspace", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert "DAEMON status=running" in result.output
    assert "stale=true" in result.output


def test_fresh_heartbeat_not_stale(tmp_path: Path) -> None:
    """Fresh heartbeat is detected as daemon_stale=false."""
    runner = CliRunner()
    _init_workspace(runner, tmp_path)

    # Write a heartbeat with status=running and recent last_seen_at
    heartbeat_path = tmp_path / ".ai-local" / "reports" / "daemon-heartbeat.json"
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    hb = {
        "status": "running",
        "mode": "loop",
        "pid": 99999,
        "started_at": now,
        "last_seen_at": now,
        "iterations": 1,
    }
    heartbeat_path.write_text(json.dumps(hb), encoding="utf-8")

    result = runner.invoke(
        app,
        ["runtime", "status", "--workspace", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert "DAEMON status=running" in result.output
    assert "stale=false" in result.output


def test_service_install_dry_run(tmp_path: Path) -> None:
    """service install --dry-run prints dry-run only and does not create service."""
    runner = CliRunner()
    _init_workspace(runner, tmp_path)

    result = runner.invoke(
        app,
        ["service", "install", "--dry-run", "--workspace", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert "SERVICE install dry-run" in result.output
    assert "NAME AI Local Agent Runtime" in result.output
    assert "NOTE dry-run only" in result.output


def test_demo_run_daemon(tmp_path: Path) -> None:
    """demo run daemon exits 0 and writes demo-daemon.json."""
    runner = CliRunner()
    _init_workspace(runner, tmp_path)

    result = runner.invoke(
        app,
        ["demo", "run", "daemon", "--workspace", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output

    assert "DEMO daemon" in result.output
    assert "STEP init PASS" in result.output
    assert "STEP task_submit PASS" in result.output
    assert "STEP daemon_loop PASS" in result.output
    assert "STEP runtime_status PASS" in result.output
    assert "STEP runtime_logs PASS" in result.output
    assert "STEP runtime_snapshot PASS" in result.output
    assert "REPORT" in result.output

    report_path = tmp_path / ".ai-local" / "reports" / "demo-daemon.json"
    assert report_path.exists()
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["status"] == "pass"
    step_names = [s["name"] for s in data["steps"]]
    assert "init" in step_names
    assert "task_submit" in step_names
    assert "daemon_loop" in step_names
    assert "runtime_status" in step_names
    assert "runtime_logs" in step_names
    assert "runtime_snapshot" in step_names
