"""Test doubles shared by several test modules."""

from __future__ import annotations

import re
import zlib
from collections.abc import Sequence
from typing import Any

import numpy as np

from rag_etat_civil.embeddings.base import Embedder, Vectors
from rag_etat_civil.llm.base import LLMProvider


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


class FakeLLM(LLMProvider):
    """A language model that returns prepared answers, one per call, and records the calls."""

    def __init__(self, *answers: str) -> None:
        self._answers = list(answers)
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    @property
    def model_id(self) -> str:
        return "fake:scripted"

    def generate_json(self, system_prompt: str, user_prompt: str, schema: dict[str, Any]) -> str:
        self.calls.append((system_prompt, user_prompt, schema))
        if not self._answers:
            raise AssertionError("FakeLLM was called more times than it has prepared answers")
        return self._answers.pop(0)
