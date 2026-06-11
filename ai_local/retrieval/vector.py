from __future__ import annotations

from hashlib import sha256
from math import sqrt
from typing import Any, Protocol

from ai_local.indexer.models import IndexedChunk
from ai_local.llm.ollama import OllamaClient, OllamaError


class VectorCandidateProvider(Protocol):
    def search(self, query: str, *, limit: int) -> list[IndexedChunk]: ...


class NullVectorProvider:
    def search(self, query: str, *, limit: int) -> list[IndexedChunk]:
        del query, limit
        return []


class TextEmbedder(Protocol):
    name: str
    dimensions: int

    def embed(self, text: str) -> list[float]: ...


class HashingTextEmbedder:
    """Deterministic SHA-256 based embedder (test/offline fallback)."""

    name = "hashing-text-v1"

    def __init__(self, dimensions: int = 32) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in text.casefold().split():
            digest = sha256(token.encode("utf-8")).digest()
            slot = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[slot] += 1.0 if digest[4] % 2 == 0 else -1.0
        magnitude = sqrt(sum(value * value for value in vector))
        return [value / magnitude for value in vector] if magnitude else vector


class OllamaEmbedder:
    """Real embedding via Ollama's nomic-embed-text model."""

    def __init__(
        self,
        client: OllamaClient,
        model: str = "nomic-embed-text:latest",
        dimensions: int = 768,
    ) -> None:
        self._client = client
        self._model = model
        self.dimensions = dimensions

    @property
    def name(self) -> str:
        return f"ollama:{self._model}"

    def embed(self, text: str) -> list[float]:
        try:
            result = self._client.embed(text, model=self._model)
            # Truncate or pad to expected dimensions
            if len(result) > self.dimensions:
                result = result[: self.dimensions]
            elif len(result) < self.dimensions:
                result = result + [0.0] * (self.dimensions - len(result))
            return result
        except OllamaError:
            # Fallback to hashing if Ollama unavailable
            hasher = HashingTextEmbedder(dimensions=self.dimensions)
            return hasher.embed(text)
