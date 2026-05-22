from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from ai_local.config.loader import load_yaml
from ai_local.harness.models import GateLevel


@dataclass(frozen=True)
class GateResult:
    command_id: str
    exit_code: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        return self.exit_code == 0


@dataclass(frozen=True)
class GateLevelResult:
    level: str
    results: list[GateResult]
    promoted: bool

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)


def load_tool_commands(config_path: Path) -> dict[str, list[str]]:
    data = load_yaml(config_path)
    tools = data.get("tools", {})
    commands: dict[str, list[str]] = {}
    for tool_id, definition in tools.items():
        command = definition.get("command")
        if isinstance(command, list) and all(isinstance(part, str) for part in command):
            commands[tool_id] = command
    return commands


def load_tool_definitions(config_path: Path) -> dict[str, dict[str, object]]:
    data = load_yaml(config_path)
    tools = data.get("tools", {})
    if not isinstance(tools, dict):
        return {}
    return {
        tool_id: definition
        for tool_id, definition in tools.items()
        if isinstance(tool_id, str) and isinstance(definition, dict)
    }


def load_gate_levels(config_path: Path) -> list[GateLevel]:
    data = load_yaml(config_path)
    levels = data.get("gate_levels", {})
    order = data.get("promotion_order", [])
    if not isinstance(levels, dict) or not isinstance(order, list):
        msg = f"Invalid gate config in {config_path}"
        raise ValueError(msg)

    loaded: list[GateLevel] = []
    for level_name in order:
        if not isinstance(level_name, str):
            continue
        definition = levels.get(level_name)
        if not isinstance(definition, dict):
            continue
        loaded.append(GateLevel(name=level_name, **definition))
    return loaded


def run_command(command_id: str, argv: list[str], cwd: Path, timeout_seconds: int) -> GateResult:
    normalized_argv = normalize_python_tool_argv(argv)
    env = _command_env(argv, cwd)
    completed = subprocess.run(
        normalized_argv,
        cwd=cwd,
        env=env,
        timeout=timeout_seconds,
        capture_output=True,
        text=True,
        check=False,
    )
    return GateResult(
        command_id=command_id,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def normalize_python_tool_argv(argv: list[str]) -> list[str]:
    if not argv:
        return argv
    if argv[0] in {"pytest", "ruff", "mypy"}:
        return [sys.executable, "-m", *argv]
    return argv


def _command_env(argv: list[str], cwd: Path) -> dict[str, str] | None:
    if not argv or argv[0] != "pytest":
        return None
    temp_root = cwd / ".pytest-tool-temp"
    temp_root.mkdir(exist_ok=True)
    env = dict(os.environ)
    env["TMP"] = str(temp_root)
    env["TEMP"] = str(temp_root)
    return env


def run_patch_gate(
    command_ids: list[str],
    *,
    config_path: Path,
    cwd: Path,
    timeout_seconds: int = 120,
) -> list[GateResult]:
    commands = load_tool_commands(config_path)
    definitions = load_tool_definitions(config_path)
    results: list[GateResult] = []
    for command_id in command_ids:
        argv = commands.get(command_id)
        if argv is None:
            results.append(
                GateResult(
                    command_id=command_id,
                    exit_code=127,
                    stdout="",
                    stderr=f"Unknown command id: {command_id}",
                )
            )
            continue
        enabled_path = definitions.get(command_id, {}).get("enabled_if_path_exists")
        if isinstance(enabled_path, str) and not (cwd / enabled_path).exists():
            results.append(
                GateResult(
                    command_id=command_id,
                    exit_code=0,
                    stdout=f"Skipped because {enabled_path} does not exist",
                    stderr="",
                )
            )
            continue
        results.append(run_command(command_id, argv, cwd, timeout_seconds))
    return results


def run_promoted_gates(
    *,
    gates_config_path: Path,
    tools_config_path: Path,
    cwd: Path,
    max_level: str | None = None,
    timeout_seconds: int = 120,
) -> list[GateLevelResult]:
    levels = load_gate_levels(gates_config_path)
    promoted_results: list[GateLevelResult] = []

    for level in levels:
        results = run_patch_gate(
            level.commands,
            config_path=tools_config_path,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
        )
        passed = all(result.passed for result in results)
        promoted_results.append(GateLevelResult(level=level.name, results=results, promoted=passed))

        if level.name == max_level:
            break
        if level.required_to_promote and not passed:
            break

    return promoted_results
