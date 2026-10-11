"""Test doubles shared by several test modules."""

from __future__ import annotations

import re
import zlib
from collections.abc import Sequence

import numpy as np

from rag_etat_civil.embeddings.base import Embedder, Vectors


class HashingEmbedder(Embedder):
    """A tiny embedder that needs no model: each word is hashed into one dimension.

    Two texts sharing words get similar vectors, which is enough to test the search logic.
    """

    def __init__(self, dimension: int = 256) -> None:
        self._dimension = dimension

    @property
    def model_id(self) -> str:
        return f"fake:hashing-{self._dimension}"

    @property
    def dimension(self) -> int:
        return self._dimension

    def _vector(self, text: str) -> Vectors:
        vector = np.zeros(self._dimension, dtype=np.float32)
        for word in re.findall(r"\w+", text.lower()):
            vector[zlib.crc32(word.encode()) % self._dimension] += 1.0
        norm = np.linalg.norm(vector)
        return vector / norm if norm else vector

    def embed_documents(self, texts: Sequence[str]) -> Vectors:
        return np.vstack([self._vector(t) for t in texts])

    def embed_query(self, text: str) -> Vectors:
        return self._vector(text)
