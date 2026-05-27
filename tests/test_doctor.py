from __future__ import annotations

from pathlib import Path

from ai_local.doctor import run_doctor
from typer.testing import CliRunner

from ai_local.cli import app

ROOT = Path(__file__).resolve().parents[1]


def test_run_doctor_finds_golden_tasks() -> None:
    report = run_doctor(root=ROOT, check_ollama=False)
    golden = next(check for check in report.checks if check.name == "golden_tasks")
    assert golden.passed
    assert "tasks" in golden.detail


def test_doctor_cli_skip_ollama() -> None:
    result = CliRunner().invoke(
        app,
        ["doctor", "--skip-ollama", "--skip-ripgrep"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "PASS doctor" in result.output or "FAIL doctor" in result.output
