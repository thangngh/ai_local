"""Retrieval package.

Provides embedder selection and retrieval factories.
"""
from __future__ import annotations

from ai_local.llm.ollama import OllamaClient
from ai_local.retrieval.vector import (
    HashingTextEmbedder,
    NullVectorProvider,
    OllamaEmbedder,
    TextEmbedder,
    VectorCandidateProvider,
)


def create_embedder(
    ollama_client: OllamaClient | None = None,
    *,
    model: str = "nomic-embed-text:latest",
    dimensions: int = 768,
) -> TextEmbedder:
    """Create the best available embedder.

    Prefers Ollama's nomic-embed-text when client is available,
    falls back to deterministic HashingTextEmbedder.
    """
    if ollama_client is not None:
        try:
            ollama_client.ensure_model(model)
            return OllamaEmbedder(ollama_client, model=model, dimensions=dimensions)
        except Exception:
            pass
    return HashingTextEmbedder(dimensions=dimensions)


def create_vector_provider(
    embedder: TextEmbedder,
    *,
    db_path: str | None = None,
) -> VectorCandidateProvider:
    """Create a vector candidate provider.

    Returns a SqliteVecProvider if sqlite_vec extension is available,
    otherwise NullVectorProvider.
    """
    if db_path is None or isinstance(embedder, HashingTextEmbedder):
        return NullVectorProvider()

    try:
        from ai_local.retrieval.sqlite_vec import SqliteVecProvider

        if SqliteVecProvider.is_available():
            from pathlib import Path

            return SqliteVecProvider(Path(db_path), embedder)
    except Exception:
        pass

    return NullVectorProvider()


__all__ = [
    "HashingTextEmbedder",
    "NullVectorProvider",
    "OllamaEmbedder",
    "TextEmbedder",
    "VectorCandidateProvider",
    "create_embedder",
    "create_vector_provider",
]
