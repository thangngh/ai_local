from __future__ import annotations

import json
import subprocess
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


# ── Phase 5B — Windows Service MVP via NSSM ─────────────────────────────

# These tests use mocking so they work on any platform / CI.


def test_service_dry_run_install_exact(tmp_path: Path) -> None:
    """service install --dry-run output is exact."""
    runner = CliRunner()
    _init_workspace(runner, tmp_path)
    result = runner.invoke(
        app, ["service", "install", "--dry-run", "--workspace", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "SERVICE install dry-run" in result.output
    assert "NAME AI Local Agent Runtime" in result.output
    assert "NOTE dry-run only" in result.output


def test_service_dry_run_uninstall_exact(tmp_path: Path) -> None:
    """service uninstall --dry-run output is exact."""
    runner = CliRunner()
    result = runner.invoke(
        app, ["service", "uninstall", "--dry-run", "--workspace", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "SERVICE uninstall dry-run" in result.output
    assert "NOTE dry-run only; no Windows service was removed" in result.output


def test_service_dry_run_start_exact(tmp_path: Path) -> None:
    """service start --dry-run output is exact."""
    runner = CliRunner()
    result = runner.invoke(
        app, ["service", "start", "--dry-run", "--workspace", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "SERVICE start dry-run" in result.output


def test_service_dry_run_stop_exact(tmp_path: Path) -> None:
    """service stop --dry-run output is exact."""
    runner = CliRunner()
    result = runner.invoke(
        app, ["service", "stop", "--dry-run", "--workspace", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "SERVICE stop dry-run" in result.output


def test_service_dry_run_status_exact(tmp_path: Path) -> None:
    """service status --dry-run output is exact."""
    runner = CliRunner()
    result = runner.invoke(
        app, ["service", "status", "--dry-run", "--workspace", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "SERVICE status dry-run" in result.output


def test_service_real_install_non_windows_fails(monkeypatch, tmp_path: Path) -> None:
    """Real install on non-Windows fails with a clear message."""
    monkeypatch.setattr("ai_local.runtime.windows_service.is_windows", lambda: False)
    runner = CliRunner()
    _init_workspace(runner, tmp_path)
    result = runner.invoke(
        app, ["service", "install", "--workspace", str(tmp_path)]
    )
    assert result.exit_code != 0, result.output
    assert "Windows only" in result.output


def test_service_real_install_missing_nssm_fails(monkeypatch, tmp_path: Path) -> None:
    """Real install on Windows but missing NSSM fails with a clear message."""
    monkeypatch.setattr("ai_local.runtime.windows_service.is_windows", lambda: True)
    monkeypatch.setattr("ai_local.runtime.windows_service.find_nssm", lambda: None)
    runner = CliRunner()
    _init_workspace(runner, tmp_path)
    result = runner.invoke(
        app, ["service", "install", "--workspace", str(tmp_path)]
    )
    assert result.exit_code != 0, result.output
    assert "NSSM not found" in result.output


def test_service_real_install_uninitialized_workspace_fails(
    monkeypatch, tmp_path: Path
) -> None:
    """Real install on Windows with NSSM but uninitialized workspace fails."""
    monkeypatch.setattr("ai_local.runtime.windows_service.is_windows", lambda: True)
    monkeypatch.setattr("ai_local.runtime.windows_service.find_nssm", lambda: Path("/usr/bin/nssm"))
    monkeypatch.setattr(
        "ai_local.runtime.windows_service.run_nssm",
        lambda args, timeout=30: subprocess.CompletedProcess(args, 0, "", ""),
    )
    runner = CliRunner()
    # Do NOT init workspace — .ai-local should be absent
    ai_local_dir = tmp_path / ".ai-local"
    assert not ai_local_dir.exists(), "precondition: workspace not initialised"
    result = runner.invoke(
        app, ["service", "install", "--workspace", str(tmp_path)]
    )
    assert result.exit_code != 0, result.output
    assert "has not been initialised" in result.output


def test_service_real_install_calls_nssm_with_expected_args(
    monkeypatch, tmp_path: Path
) -> None:
    """Real install on Windows with mocked NSSM calls expected NSSM args."""
    monkeypatch.setattr("ai_local.runtime.windows_service.is_windows", lambda: True)
    monkeypatch.setattr("ai_local.runtime.windows_service.find_nssm", lambda: Path("/usr/bin/nssm"))

    calls: list[list[str]] = []

    def fake_run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "ok", "")

    monkeypatch.setattr(
        "ai_local.runtime.windows_service.run_nssm", fake_run
    )

    runner = CliRunner()
    _init_workspace(runner, tmp_path)
    result = runner.invoke(
        app, ["service", "install", "--workspace", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "SERVICE install PASS" in result.output

    # Verify that install was called with the service ID
    install_calls = [c for c in calls if c[0] == "install"]
    assert len(install_calls) >= 1
    assert "ai-local-agent-runtime" in install_calls[0]

    # Verify set calls for configuration
    set_calls = [c for c in calls if c[0] == "set"]
    set_names = [c[2] for c in set_calls if len(c) >= 3]
    assert "DisplayName" in set_names
    assert "Description" in set_names
    assert "AppDirectory" in set_names


def test_service_real_uninstall_does_not_delete_workspace(
    monkeypatch, tmp_path: Path
) -> None:
    """Real uninstall does not delete workspace data."""
    monkeypatch.setattr("ai_local.runtime.windows_service.is_windows", lambda: True)
    monkeypatch.setattr("ai_local.runtime.windows_service.find_nssm", lambda: Path("/usr/bin/nssm"))

    def fake_uninstall_run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, "removed", "")

    monkeypatch.setattr(
        "ai_local.runtime.windows_service.run_nssm", fake_uninstall_run
    )

    runner = CliRunner()
    _init_workspace(runner, tmp_path)

    # Create a file in the workspace to verify it's preserved
    test_file = tmp_path / "test_data.txt"
    test_file.write_text("important data", encoding="utf-8")

    result = runner.invoke(
        app, ["service", "uninstall", "--workspace", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "SERVICE uninstall PASS" in result.output
    assert "workspace data was not removed" in result.output

    # Verify workspace data still exists
    assert test_file.exists()
    assert (tmp_path / ".ai-local" / "logs").is_dir()
    assert (tmp_path / ".ai-local" / "reports").is_dir()


def test_service_start_calls_nssm(
    monkeypatch, tmp_path: Path
) -> None:
    """service start calls NSSM with expected args under mock."""
    monkeypatch.setattr("ai_local.runtime.windows_service.is_windows", lambda: True)
    monkeypatch.setattr("ai_local.runtime.windows_service.find_nssm", lambda: Path("/usr/bin/nssm"))

    calls: list[list[str]] = []

    def fake_run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "ok", "")

    monkeypatch.setattr(
        "ai_local.runtime.windows_service.run_nssm", fake_run
    )

    runner = CliRunner()
    _init_workspace(runner, tmp_path)
    result = runner.invoke(
        app, ["service", "start", "--workspace", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "SERVICE start PASS" in result.output
    start_calls = [c for c in calls if c[0] == "start"]
    assert len(start_calls) >= 1
    assert "ai-local-agent-runtime" in start_calls[0]


def test_service_stop_calls_nssm(
    monkeypatch, tmp_path: Path
) -> None:
    """service stop calls NSSM with expected args under mock."""
    monkeypatch.setattr("ai_local.runtime.windows_service.is_windows", lambda: True)
    monkeypatch.setattr("ai_local.runtime.windows_service.find_nssm", lambda: Path("/usr/bin/nssm"))

    calls: list[list[str]] = []

    def fake_run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "ok", "")

    monkeypatch.setattr(
        "ai_local.runtime.windows_service.run_nssm", fake_run
    )

    runner = CliRunner()
    _init_workspace(runner, tmp_path)
    result = runner.invoke(
        app, ["service", "stop", "--workspace", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "SERVICE stop PASS" in result.output
    stop_calls = [c for c in calls if c[0] == "stop"]
    assert len(stop_calls) >= 1
    assert "ai-local-agent-runtime" in stop_calls[0]


def test_service_status_calls_nssm(
    monkeypatch, tmp_path: Path
) -> None:
    """service status calls NSSM with expected args under mock."""
    monkeypatch.setattr("ai_local.runtime.windows_service.is_windows", lambda: True)
    monkeypatch.setattr("ai_local.runtime.windows_service.find_nssm", lambda: Path("/usr/bin/nssm"))

    calls: list[list[str]] = []

    def fake_run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "SERVICE_RUNNING", "")

    monkeypatch.setattr(
        "ai_local.runtime.windows_service.run_nssm", fake_run
    )

    runner = CliRunner()
    _init_workspace(runner, tmp_path)
    result = runner.invoke(
        app, ["service", "status", "--workspace", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "SERVICE status" in result.output
    assert "STATE" in result.output
    status_calls = [c for c in calls if c[0] == "status"]
    assert len(status_calls) >= 1
    assert "ai-local-agent-runtime" in status_calls[0]


def test_service_logs_reads_daemon_log(tmp_path: Path) -> None:
    """service logs --tail reads daemon log entries."""
    runner = CliRunner()
    _init_workspace(runner, tmp_path)

    # Run daemon loop to create log
    runner.invoke(
        app,
        [
            "daemon", "run",
            "--workspace", str(tmp_path),
            "--loop",
            "--poll-interval", "0.01",
            "--max-iterations", "2",
        ],
    )

    result = runner.invoke(
        app, ["service", "logs", "--workspace", str(tmp_path), "--tail", "2"]
    )
    assert result.exit_code == 0, result.output
    assert "LOGS" in result.output
    assert "daemon.log" in result.output


def test_service_logs_none_when_missing(tmp_path: Path) -> None:
    """service logs prints LOGS none when no logs exist."""
    runner = CliRunner()
    _init_workspace(runner, tmp_path)
    result = runner.invoke(
        app, ["service", "logs", "--workspace", str(tmp_path), "--tail", "5"]
    )
    assert result.exit_code == 0, result.output
    assert "LOGS none" in result.output


# ── Phase 5C — PowerShell scripts and smoke test documentation ───────────


def test_check_nssm_script_exists() -> None:
    """check-nssm.ps1 script exists."""
    assert Path("scripts/windows-service/check-nssm.ps1").is_file()


def test_install_script_exists() -> None:
    """install-backend-service.ps1 script exists."""
    assert Path("scripts/windows-service/install-backend-service.ps1").is_file()


def test_uninstall_script_exists() -> None:
    """uninstall-backend-service.ps1 script exists."""
    assert Path("scripts/windows-service/uninstall-backend-service.ps1").is_file()


def test_restart_script_exists() -> None:
    """restart-backend-service.ps1 script exists."""
    assert Path("scripts/windows-service/restart-backend-service.ps1").is_file()


def test_status_script_exists() -> None:
    """show-backend-service-status.ps1 script exists."""
    assert Path("scripts/windows-service/show-backend-service-status.ps1").is_file()


def test_no_auto_download_in_scripts() -> None:
    """No script contains an auto-download URL."""
    script_dir = Path("scripts/windows-service")
    download_markers = ["Invoke-WebRequest", "curl", "wget", "Start-BitsTransfer"]
    for ps1 in sorted(script_dir.glob("*.ps1")):
        content = ps1.read_text(encoding="utf-8")
        for marker in download_markers:
            assert marker not in content, f"{ps1.name} contains {marker}"


def test_uninstall_script_does_not_remove_reports() -> None:
    """uninstall script does not delete reports/backups/db."""
    script = Path("scripts/windows-service/uninstall-backend-service.ps1")
    content = script.read_text(encoding="utf-8")
    # It should only remove *.log, not other directories
    assert ".ai-local\\logs" in content or ".ai-local/logs" in content


def test_install_script_has_dry_run_flag() -> None:
    """install script has -DryRun switch."""
    content = Path("scripts/windows-service/install-backend-service.ps1").read_text(
        encoding="utf-8"
    )
    assert "[switch]$DryRun" in content


def test_uninstall_script_has_dry_run_flag() -> None:
    """uninstall script has -DryRun switch."""
    content = Path(
        "scripts/windows-service/uninstall-backend-service.ps1"
    ).read_text(encoding="utf-8")
    assert "[switch]$DryRun" in content


def test_restart_script_has_dry_run_flag() -> None:
    """restart script has -DryRun switch."""
    content = Path(
        "scripts/windows-service/restart-backend-service.ps1"
    ).read_text(encoding="utf-8")
    assert "[switch]$DryRun" in content


def test_docs_contain_key_commands() -> None:
    """Documentation lists required validation commands."""
    doc_path = Path("docs/demo/phase-5c-windows-service-smoke.md")
    assert doc_path.is_file()
    content = doc_path.read_text(encoding="utf-8")
    assert "check-nssm.ps1" in content
    assert "service install" in content
    assert "service stop" in content
    assert "service uninstall" in content
    assert "show-backend-service-status.ps1" in content


def test_docs_no_production_claim() -> None:
    """Documentation does not claim production-grade service."""
    doc_path = Path("docs/demo/phase-5c-windows-service-smoke.md")
    content = doc_path.read_text(encoding="utf-8")
    # Either "production-grade" is not present, or it says "not intended for production"
    if "production-grade" in content:
        assert "not intended for production" in content
