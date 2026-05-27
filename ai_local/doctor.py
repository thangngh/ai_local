from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from ai_local.benchmark.runner import discover_golden_tasks
from ai_local.llm.ollama import OllamaClient, OllamaConfig, OllamaError
from ai_local.retrieval.ripgrep import ripgrep_available, ripgrep_version


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    passed: bool
    detail: str
    critical: bool = True


@dataclass(frozen=True)
class DoctorReport:
    checks: list[DoctorCheck]

    @property
    def passed(self) -> bool:
        return all(check.passed or not check.critical for check in self.checks)

    @property
    def failed_critical(self) -> list[DoctorCheck]:
        return [check for check in self.checks if check.critical and not check.passed]


def run_doctor(
    *,
    root: Path,
    ollama_base_url: str = "http://127.0.0.1:11434",
    ollama_model: str = "qwen2.5:0.5b",
    check_ollama: bool = True,
    check_ripgrep: bool = True,
) -> DoctorReport:
    checks: list[DoctorCheck] = []
    checks.append(_check_python_version())
    checks.append(_check_package_import())
    if check_ripgrep:
        checks.append(_check_ripgrep())
    else:
        checks.append(
            DoctorCheck(name="ripgrep", passed=True, detail="skipped", critical=False)
        )
    if check_ollama:
        checks.extend(_check_ollama(base_url=ollama_base_url, model=ollama_model))
    else:
        checks.append(
            DoctorCheck(
                name="ollama",
                passed=True,
                detail="skipped",
                critical=False,
            )
        )
    checks.append(_check_sqlite_writable(root))
    checks.append(_check_golden_tasks(root))
    return DoctorReport(checks=checks)


def _check_python_version() -> DoctorCheck:
    ok = sys.version_info >= (3, 11)
    detail = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return DoctorCheck(name="python", passed=ok, detail=detail)


def _check_package_import() -> DoctorCheck:
    try:
        import ai_local  # noqa: F401
    except ImportError as exc:
        return DoctorCheck(name="package", passed=False, detail=str(exc))
    return DoctorCheck(name="package", passed=True, detail="ai_local import ok")


def _check_ripgrep() -> DoctorCheck:
    if not ripgrep_available():
        return DoctorCheck(
            name="ripgrep",
            passed=False,
            detail="rg not found on PATH; install via winget install BurntSushi.ripgrep.MSVC",
        )
    return DoctorCheck(name="ripgrep", passed=True, detail=ripgrep_version() or "rg available")


def _check_ollama(*, base_url: str, model: str) -> list[DoctorCheck]:
    client = OllamaClient(OllamaConfig(base_url=base_url, model=model))
    if not client.health_check():
        return [
            DoctorCheck(
                name="ollama",
                passed=False,
                detail=f"unreachable at {base_url}",
            )
        ]
    try:
        client.ensure_model(model)
    except OllamaError as exc:
        return [
            DoctorCheck(name="ollama", passed=True, detail=f"reachable at {base_url}"),
            DoctorCheck(name="ollama_model", passed=False, detail=str(exc)),
        ]
    return [
        DoctorCheck(name="ollama", passed=True, detail=f"reachable at {base_url}"),
        DoctorCheck(name="ollama_model", passed=True, detail=model),
    ]


def _check_sqlite_writable(root: Path) -> DoctorCheck:
    probe_dir = root / ".reports" / "doctor-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    db_path = probe_dir / "probe.db"
    try:
        connection = sqlite3.connect(db_path)
        connection.execute("CREATE TABLE IF NOT EXISTS probe (id INTEGER PRIMARY KEY)")
        connection.commit()
        connection.close()
        db_path.unlink(missing_ok=True)
    except OSError as exc:
        return DoctorCheck(name="sqlite", passed=False, detail=str(exc))
    return DoctorCheck(name="sqlite", passed=True, detail=str(probe_dir))


def _check_golden_tasks(root: Path) -> DoctorCheck:
    tasks_root = root / "golden_tasks"
    try:
        tasks = discover_golden_tasks(tasks_root)
    except (FileNotFoundError, OSError) as exc:
        return DoctorCheck(name="golden_tasks", passed=False, detail=str(exc))
    return DoctorCheck(name="golden_tasks", passed=True, detail=f"{len(tasks)} tasks")
