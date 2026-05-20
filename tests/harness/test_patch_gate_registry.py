from pathlib import Path

import sys

from ai_local.harness.test_gate import (
    load_gate_levels,
    load_tool_definitions,
    load_tool_commands,
    normalize_python_tool_argv,
)


ROOT = Path(__file__).resolve().parents[2]


def test_patch_gate_can_resolve_quality_commands() -> None:
    commands = load_tool_commands(ROOT / "configs" / "tools.yaml")

    assert commands["test.pytest"] == ["pytest"]
    assert commands["test.harness"] == ["pytest", "tests/harness"]
    assert commands["test.ruff"] == ["ruff", "check"]
    assert commands["test.mypy"] == ["mypy", "ai_local", "tests"]


def test_patch_gate_runs_python_tools_through_current_interpreter() -> None:
    assert normalize_python_tool_argv(["pytest"]) == [sys.executable, "-m", "pytest"]
    assert normalize_python_tool_argv(["ruff", "check"]) == [
        sys.executable,
        "-m",
        "ruff",
        "check",
    ]


def test_gate_levels_promote_from_easy_to_extreme() -> None:
    levels = load_gate_levels(ROOT / "configs" / "gates.yaml")

    assert [level.name for level in levels] == ["easy", "medium", "hard", "extreme"]
    assert levels[0].commands == ["test.harness"]
    assert levels[1].commands == ["test.pytest"]
    assert levels[2].commands == ["test.ruff", "test.mypy"]
    assert levels[3].commands == ["test.npm"]


def test_extreme_npm_gate_is_conditionally_enabled() -> None:
    definitions = load_tool_definitions(ROOT / "configs" / "tools.yaml")

    assert definitions["test.npm"]["enabled_if_path_exists"] == "package.json"
