from __future__ import annotations

from pathlib import Path

from ai_local.config.workspace import get_ollama_config
from ai_local.llm.ollama import OllamaClient, OllamaConfig, OllamaError


def build_worker_ollama_client(
    *,
    workspace: Path,
    enabled: bool,
    model: str | None = None,
    base_url: str | None = None,
) -> OllamaClient | None:
    if not enabled:
        return None
    config_data = get_ollama_config(workspace)
    resolved_model = model or str(config_data.get("model", "qwen2.5:0.5b"))
    resolved_base_url = base_url or str(config_data.get("base_url", "http://127.0.0.1:11434"))
    client = OllamaClient(OllamaConfig(base_url=resolved_base_url, model=resolved_model))
    if not client.health_check():
        raise OllamaError(f"Ollama unreachable at {resolved_base_url}")
    client.ensure_model()
    return client
