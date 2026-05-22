from hashlib import sha256
from math import sqrt
from typing import Protocol

from ai_local.indexer.models import IndexedChunk


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
