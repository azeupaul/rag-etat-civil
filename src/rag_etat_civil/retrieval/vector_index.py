"""The contract of a vector index: store passage vectors and find the closest ones."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import NamedTuple, Self

from rag_etat_civil.embeddings.base import Embedder, Vectors


class Match(NamedTuple):
    """One search result: the id of a chunk and its similarity to the query."""

    id: str
    score: float


class IndexMismatchError(RuntimeError):
    """The index was built with another embedding model than the one configured."""


class VectorIndex(ABC):
    """Stores one vector per chunk id and answers nearest-neighbour queries.

    Vectors and queries are L2-normalized (see `Embedder`), so the score of a match is a
    cosine similarity: 1.0 for identical directions, close to 0 for unrelated texts.
    """

    @property
    @abstractmethod
    def model_id(self) -> str:
        """The embedding model that produced the vectors."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Length of the stored vectors."""

    @abstractmethod
    def __len__(self) -> int:
        """Number of vectors stored."""

    @abstractmethod
    def search(self, query: Vectors, k: int) -> list[Match]:
        """Return the `k` closest chunks, best first (fewer if the index is smaller)."""

    @abstractmethod
    def save(self, directory: Path) -> None:
        """Write the index in `directory` (created if needed)."""

    @classmethod
    @abstractmethod
    def load(cls, directory: Path) -> Self:
        """Read an index written by `save`."""

    def check_compatible(self, embedder: Embedder) -> None:
        """Refuse to use an index with a model whose vectors live in another space.

        Vectors of two different models cannot be compared: the search would still return
        results, but meaningless ones. Better to stop with a clear message.
        """
        if self.model_id != embedder.model_id or self.dimension != embedder.dimension:
            raise IndexMismatchError(
                f"The index was built with {self.model_id!r} ({self.dimension} dimensions) "
                f"but the configured model is {embedder.model_id!r} "
                f"({embedder.dimension} dimensions). Rebuild the index with `make index`."
            )
