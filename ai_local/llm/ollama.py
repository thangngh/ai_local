from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from ai_local.llm.tokens import TokenUsage, estimate_tokens


class OllamaError(RuntimeError):
    pass


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5:0.5b"
    timeout_seconds: int = 120


@dataclass(frozen=True)
class OllamaChatResult:
    content: str
    latency_ms: int
    model: str
    token_usage: TokenUsage
    total_duration_ns: int | None = None
    prompt_eval_duration_ns: int | None = None
    eval_duration_ns: int | None = None


class OllamaClient:
    def __init__(self, config: OllamaConfig | None = None) -> None:
        self._config = config or OllamaConfig()
        self._base = self._config.base_url.rstrip("/")

    @property
    def model(self) -> str:
        return self._config.model

    def health_check(self) -> bool:
        try:
            self._request("GET", "/api/tags", payload=None)
        except OllamaError:
            return False
        return True

    def list_models(self) -> list[str]:
        payload = self._request("GET", "/api/tags", payload=None)
        models = payload.get("models", [])
        names: list[str] = []
        for item in models:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                names.append(item["name"])
        return names

    def ensure_model(self, model: str | None = None) -> None:
        target = model or self._config.model
        available = self.list_models()
        if target not in available:
            msg = (
                f"Ollama model {target!r} is not available. "
                f"Installed models: {', '.join(available) or '(none)'}"
            )
            raise OllamaError(msg)

    def chat(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        messages: list[dict[str, str]] | None = None,
    ) -> OllamaChatResult:
        target = model or self._config.model
        started = time.perf_counter()
        chat_messages = messages or [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        payload = self._request(
            "POST",
            "/api/chat",
            payload={
                "model": target,
                "messages": chat_messages,
                "stream": False,
                "options": {"temperature": 0},
            },
        )
        message = payload.get("message", {})
        content = message.get("content", "") if isinstance(message, dict) else ""
        if not isinstance(content, str):
            content = str(content)
        latency_ms = int((time.perf_counter() - started) * 1000)
        prompt_text = "\n".join(
            item["content"]
            for item in chat_messages
            if isinstance(item.get("content"), str)
        )
        input_tokens = _coerce_int(payload.get("prompt_eval_count"))
        output_tokens = _coerce_int(payload.get("eval_count"))
        token_source = "ollama_api"
        if input_tokens is None:
            input_tokens = estimate_tokens(prompt_text)
            token_source = "estimated"
        if output_tokens is None:
            output_tokens = estimate_tokens(content)
            token_source = "estimated"
        eval_duration_ns = _coerce_int(payload.get("eval_duration"))
        token_usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            input_chars=len(prompt_text),
            output_chars=len(content),
            token_source=token_source,
            eval_duration_ns=eval_duration_ns,
        )
        return OllamaChatResult(
            content=content.strip(),
            latency_ms=latency_ms,
            model=target,
            token_usage=token_usage,
            total_duration_ns=_coerce_int(payload.get("total_duration")),
            prompt_eval_duration_ns=_coerce_int(payload.get("prompt_eval_duration")),
            eval_duration_ns=eval_duration_ns,
        )

    def _request(self, method: str, path: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        url = f"{self._base}{path}"
        data = None
        headers = {"Content-Type": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self._config.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            msg = f"Ollama HTTP {exc.code} for {path}: {detail}"
            raise OllamaError(msg) from exc
        except urllib.error.URLError as exc:
            msg = f"Ollama unreachable at {self._base}: {exc.reason}"
            raise OllamaError(msg) from exc
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            msg = f"Ollama returned invalid JSON from {path}"
            raise OllamaError(msg) from exc
        if not isinstance(parsed, dict):
            msg = f"Ollama returned unexpected payload from {path}"
            raise OllamaError(msg)
        return parsed


def _coerce_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None
