"""Workspace configuration helpers.

Provides functions to load/save workspace-level config (including Ollama settings)
from `.ai-local/config.yaml`.  These live in a separate module to avoid the
circular import between ``cli.app`` and ``cli.commands.agent``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_OLLAMA_CONFIG: dict[str, Any] = {
    "enabled": False,
    "model": "qwen2.5:0.5b",
    "embedding_model": "nomic-embed-text:latest",
    "base_url": "http://127.0.0.1:11434",
}


def workspace_dir(workspace: Path) -> Path:
    return workspace / ".ai-local"


def ensure_workspace(workspace: Path) -> dict[str, Path]:
    base = workspace_dir(workspace)
    dirs = {
        "base": base,
        "logs": base / "logs",
        "reports": base / "reports",
        "backups": base / "backups",
    }
    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)
    return {
        **dirs,
        "config": base / "config.yaml",
        "knowledge_db": base / "knowledge.db",
        "runtime_db": base / "runtime.db",
        "tasks_db": base / "tasks.db",
        "audit_db": base / "audit.db",
    }


def load_workspace_config(workspace: Path) -> dict[str, Any]:
    """Load workspace configuration from .ai-local/config.yaml."""
    paths = ensure_workspace(workspace)
    config_path = paths["config"]
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_workspace_config(workspace: Path, config: dict[str, Any]) -> None:
    """Save workspace configuration to .ai-local/config.yaml."""
    paths = ensure_workspace(workspace)
    paths["config"].write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def get_ollama_config(workspace: Path) -> dict[str, Any]:
    """Get Ollama config from workspace, merged with defaults."""
    ws_config = load_workspace_config(workspace)
    ol_config = ws_config.get("ollama", {})
    if not isinstance(ol_config, dict):
        ol_config = {}
    merged = dict(DEFAULT_OLLAMA_CONFIG)
    merged.update(ol_config)
    return merged


def set_ollama_config(workspace: Path, **kwargs: Any) -> dict[str, Any]:
    """Update Ollama config in workspace config.yaml."""
    ws_config = load_workspace_config(workspace)
    ol_config = ws_config.get("ollama", {})
    if not isinstance(ol_config, dict):
        ol_config = {}
    ol_config.update(kwargs)
    ws_config["ollama"] = ol_config
    save_workspace_config(workspace, ws_config)
    return ol_config
