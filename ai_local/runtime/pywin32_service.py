"""Windows Service host using pywin32 (optional).

This module provides an alternative Windows Service strategy that uses
pywin32 (``win32serviceutil`` / ``win32service`` / ``win32event`` /
``servicemanager``) instead of NSSM.

Usage::

    python -m ai_local.runtime.pywin32_service install --workspace <path>
    python -m ai_local.runtime.pywin32_service start
    python -m ai_local.runtime.pywin32_service stop
    python -m ai_local.runtime.pywin32_service remove

All pywin32 imports are **lazy** — the module can be imported on any
platform without pywin32 installed.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path

SERVICE_ID = "ai-local-agent-runtime-pywin32"
SERVICE_DISPLAY_NAME = "AI Local Agent Runtime (pywin32)"
SERVICE_DESCRIPTION = "Local-first AI agent runtime daemon"
# The service class will be defined conditionally below.
SERVICE_CLASS: str | None = None

# ─── Availability helpers ─────────────────────────────────────────────────────

def _load_pywin32_modules():
    """Attempt to import pywin32 modules, returning a tuple.

    Returns ``None`` if any import fails.  The returned tuple contains the
    modules in the same order as they are used in the service class.
    """
    try:
        import servicemanager
        import win32event
        import win32service
        import win32serviceutil
    except ImportError:
        return None
    return servicemanager, win32event, win32service, win32serviceutil

_pywin32_modules = _load_pywin32_modules()

# Expose helpers for callers

def pywin32_available() -> bool:
    """Return ``True`` when pywin32 can be imported."""
    return _pywin32_modules is not None


def require_pywin32() -> None:
    """Raise :class:`RuntimeError` if pywin32 is not installed."""
    if not pywin32_available():
        raise RuntimeError(
            "pywin32 not found. Install with: python -m pip install pywin32. "
            "For Windows Service use, install in a Python environment accessible "
            "to the service account."
        )

# ─── Windows check helpers ────────────────────────────────────────────────────

def _is_windows() -> bool:
    return platform.system() == "Windows"


def _check_windows() -> None:
    if not _is_windows():
        raise RuntimeError("Windows only")

# ─── Config file helpers ─────────────────────────────────────────────────────

def _config_path(workspace: Path) -> Path:
    """Return the path to the pywin32 service config JSON file."""
    return workspace.resolve() / ".ai-local" / "reports" / "pywin32-service.json"


def write_config(workspace: Path, *, poll_interval: float = 1.0) -> dict:
    """Write the pywin32 service config JSON.

    Returns the config dict that was written.
    """
    abs_ws = workspace.resolve()
    config = {
        "workspace": str(abs_ws),
        "poll_interval": poll_interval,
        "service_id": SERVICE_ID,
    }
    path = _config_path(abs_ws)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config


def read_config(workspace: Path) -> dict | None:
    """Read the pywin32 service config, or ``None`` if missing / corrupt."""
    path = _config_path(workspace)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

# ─── Service class definition (conditional) ───────────────────────────────────
if _pywin32_modules is not None:
    servicemanager, win32event, win32service, win32serviceutil = _pywin32_modules

    class Pywin32DaemonService(win32serviceutil.ServiceFramework):
        """Windows Service host for the AI Local agent runtime daemon."""

        _svc_name_ = SERVICE_ID
        _svc_display_name_ = SERVICE_DISPLAY_NAME
        _svc_description_ = SERVICE_DESCRIPTION

        def __init__(self, args) -> None:
            win32serviceutil.ServiceFramework.__init__(self, args)
            self._stop_event = win32event.CreateEvent(None, 0, 0, None)
            self._config: dict | None = None

        def SvcDoRun(self) -> None:
            from ai_local.runtime.daemon_contract import run_daemon_loop
            import winreg

            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                0xF000,
                (self._svc_name_, "Service starting"),
            )

            # Load config from registry Parameters subkey set at install time
            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    f"SYSTEM\\CurrentControlSet\\Services\\{SERVICE_ID}\\Parameters",
                ) as key:
                    workspace_str = winreg.QueryValueEx(key, "workspace")[0]
                    poll_interval_str = winreg.QueryValueEx(key, "poll_interval")[0]
                    self._config = {
                        "workspace": workspace_str,
                        "poll_interval": float(poll_interval_str),
                    }
            except Exception as exc:
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_ERROR_TYPE,
                    0xF001,
                    (self._svc_name_, f"Failed to read config from registry: {exc}"),
                )
                return

            if self._config is None or "workspace" not in self._config:
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_ERROR_TYPE,
                    0xF001,
                    (self._svc_name_, "No config found in registry; cannot start daemon loop"),
                )
                return

            workspace = Path(self._config["workspace"])  # noqa: PLW2901
            poll_interval = self._config.get("poll_interval", 1.0)

            def emit(msg: str) -> None:
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_INFORMATION_TYPE,
                    0xF002,
                    (self._svc_name_, msg),
                )

            def should_stop() -> bool:
                return (
                    win32event.WaitForSingleObject(self._stop_event, 0)
                    == win32event.WAIT_OBJECT_0
                )

            try:
                iterations = run_daemon_loop(
                    workspace=workspace,
                    poll_interval=poll_interval,
                    should_stop=should_stop,
                    emit_line=emit,
                )
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_INFORMATION_TYPE,
                    0xF003,
                    (
                        self._svc_name_,
                        f"Daemon loop exited after {iterations} iterations",
                    ),
                )
            except Exception as exc:
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_ERROR_TYPE,
                    0xF004,
                    (self._svc_name_, f"Daemon loop error: {exc}"),
                )

        def SvcStop(self) -> None:
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                0xF005,
                (self._svc_name_, "Service stopping"),
            )
            win32event.SetEvent(self._stop_event)
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                0xF006,
                (self._svc_name_, "Service stopped"),
            )

    SERVICE_CLASS = "ai_local.runtime.pywin32_service.Pywin32DaemonService"
else:
    # Placeholder class when pywin32 is not available.
    class Pywin32DaemonService:  # type: ignore
        """Placeholder when pywin32 is not available."""

    SERVICE_CLASS = None

# ─── Install / remove / start / stop / status helpers ────────────────────────

def _workspace_ok(workspace: Path) -> Path:
    abs_ws = workspace.resolve()
    ai_local_dir = abs_ws / ".ai-local"
    if not ai_local_dir.is_dir():
        raise RuntimeError(
            f"Workspace {abs_ws} has not been initialised. "
            "Run `python -m ai_local.cli init --workspace <path>` first."
        )
    return abs_ws


def _run_python_module(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    cmd = [str(sys.executable), "-m", "ai_local.runtime.pywin32_service", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def install_pywin32_service(workspace: Path, *, startup: str = "manual") -> None:
    _check_windows()
    require_pywin32()
    abs_ws = _workspace_ok(workspace)

    write_config(abs_ws, poll_interval=1.0)

    import win32serviceutil

    start_type = (
        win32service.SERVICE_AUTO_START if startup == "auto" else win32service.SERVICE_DEMAND_START
    )
    try:
        win32serviceutil.InstallService(
            SERVICE_CLASS,
            SERVICE_ID,
            SERVICE_DISPLAY_NAME,
            startType=start_type,
        )
        win32serviceutil.SetServiceCustomOption(SERVICE_ID, "workspace", str(abs_ws))
        win32serviceutil.SetServiceCustomOption(SERVICE_ID, "poll_interval", "1.0")
    except Exception as exc:  # pragma: no cover - exercised by tests
        raise RuntimeError(f"Failed to install pywin32 service: {exc}") from exc

    # Configure the service description after installation.
    try:
        import win32service as _ws
        scm = _ws.OpenSCManager(None, None, _ws.SC_MANAGER_ALL_ACCESS)
        try:
            svc = _ws.OpenService(scm, SERVICE_ID, _ws.SERVICE_CHANGE_CONFIG)
            _ws.ChangeServiceConfig(
                svc,
                _ws.SERVICE_NO_CHANGE,
                _ws.SERVICE_NO_CHANGE,
                _ws.SERVICE_NO_CHANGE,
                None,
                None,
                0,
                None,
                None,
                None,
                SERVICE_DESCRIPTION,
            )
            _ws.CloseServiceHandle(svc)
        finally:
            _ws.CloseServiceHandle(scm)
    except Exception as exc:  # pragma: no cover - exercised by tests
        raise RuntimeError(
            f"Failed to configure pywin32 service description: {exc}"
        ) from exc


def remove_pywin32_service() -> None:
    _check_windows()
    require_pywin32()
    import win32serviceutil
    try:
        win32serviceutil.RemoveService(SERVICE_ID)
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Failed to remove pywin32 service: {exc}") from exc


def start_pywin32_service() -> None:
    _check_windows()
    require_pywin32()
    import win32serviceutil
    try:
        win32serviceutil.StartService(SERVICE_ID)
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Failed to start pywin32 service: {exc}") from exc


def stop_pywin32_service() -> None:
    _check_windows()
    require_pywin32()
    import win32serviceutil
    try:
        win32serviceutil.StopService(SERVICE_ID)
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Failed to stop pywin32 service: {exc}") from exc


def status_pywin32_service() -> str:
    _check_windows()
    require_pywin32()
    import win32serviceutil
    try:
        raw = win32serviceutil.QueryServiceStatus(SERVICE_ID)
        state_map = {
            1: "STOPPED",
            2: "START_PENDING",
            3: "STOP_PENDING",
            4: "RUNNING",
            5: "CONTINUE_PENDING",
            6: "PAUSE_PENDING",
            7: "PAUSED",
        }
        state_code = raw[1] if len(raw) > 1 else 0
        return state_map.get(state_code, f"UNKNOWN({state_code})")
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Failed to query pywin32 service: {exc}") from exc

# ─── __main__ entry point ───────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="AI Local Agent Runtime pywin32 Service host"
    )
    parser.add_argument(
        "action",
        choices=["install", "remove", "start", "stop", "status"],
        help="Service action",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Workspace path (required for install)",
    )
    parser.add_argument(
        "--startup",
        choices=["auto", "manual"],
        default="manual",
        help="Startup type for install (default: manual)",
    )

    args = parser.parse_args()

    if args.action == "install":
        if args.workspace is None:
            print("ERROR: --workspace is required for install")
            sys.exit(1)
        try:
            install_pywin32_service(args.workspace, startup=args.startup)
            print("SERVICE install PASS")
            print("STRATEGY pywin32")
            print(f"NAME {SERVICE_DISPLAY_NAME}")
            print(f"ID {SERVICE_ID}")
            print(f"WORKSPACE {args.workspace.resolve()}")
        except RuntimeError as exc:
            print(f'SERVICE install FAIL reason="{exc}"')
            sys.exit(1)

    elif args.action == "remove":
        try:
            remove_pywin32_service()
            print("SERVICE uninstall PASS")
            print("STRATEGY pywin32")
            print(f"NAME {SERVICE_DISPLAY_NAME}")
            print(f"ID {SERVICE_ID}")
            print("NOTE workspace data was not removed")
        except RuntimeError as exc:
            print(f'SERVICE uninstall FAIL reason="{exc}"')
            sys.exit(1)

    elif args.action == "start":
        try:
            start_pywin32_service()
            print("SERVICE start PASS")
            print("STRATEGY pywin32")
            print(f"NAME {SERVICE_DISPLAY_NAME}")
            print(f"ID {SERVICE_ID}")
        except RuntimeError as exc:
            print(f'SERVICE start FAIL reason="{exc}"')
            sys.exit(1)

    elif args.action == "stop":
        try:
            stop_pywin32_service()
            print("SERVICE stop PASS")
            print("STRATEGY pywin32")
            print(f"NAME {SERVICE_DISPLAY_NAME}")
            print(f"ID {SERVICE_ID}")
        except RuntimeError as exc:
            print(f'SERVICE stop FAIL reason="{exc}"')
            sys.exit(1)

    elif args.action == "status":
        try:
            state = status_pywin32_service()
            print("SERVICE status")
            print("STRATEGY pywin32")
            print(f"NAME {SERVICE_DISPLAY_NAME}")
            print(f"ID {SERVICE_ID}")
            print(f"STATE {state}")
        except RuntimeError as exc:
            print(f'SERVICE status FAIL reason="{exc}"')
            sys.exit(1)


if __name__ == "__main__":
    main()
