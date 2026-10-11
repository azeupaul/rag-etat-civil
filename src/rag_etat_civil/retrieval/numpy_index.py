"""A vector index kept in a numpy matrix.

With a few hundred vectors, a matrix product is all we need: no server, no extra dependency.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Self

import numpy as np

from rag_etat_civil.embeddings.base import Vectors
from rag_etat_civil.retrieval.vector_index import Match, VectorIndex

FORMAT_VERSION = 1
VECTORS_FILE = "vectors.npy"
META_FILE = "meta.json"


class NumpyIndex(VectorIndex):
    def __init__(self, ids: Sequence[str], vectors: Vectors, model_id: str) -> None:
        if vectors.ndim != 2 or vectors.shape[0] != len(ids):
            raise ValueError(
                f"Expected one vector per id: got {len(ids)} ids and vectors of shape "
                f"{vectors.shape}"
            )
        if len(set(ids)) != len(ids):
            raise ValueError("Chunk ids must be unique")
        self._ids = list(ids)
        self._vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def dimension(self) -> int:
        return int(self._vectors.shape[1])

    def __len__(self) -> int:
        return len(self._ids)

    def search(self, query: Vectors, k: int) -> list[Match]:
        if query.shape != (self.dimension,):
            raise ValueError(f"Expected a query of shape ({self.dimension},), got {query.shape}")
        scores = self._vectors @ query
        # A stable sort keeps the original order between equal scores: results are reproducible.
        best = np.argsort(-scores, kind="stable")[:k]
        return [Match(self._ids[i], float(scores[i])) for i in best]

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.save(directory / VECTORS_FILE, self._vectors)
        meta = {
            "format": FORMAT_VERSION,
            "model_id": self._model_id,
            "dimension": self.dimension,
            "ids": self._ids,
        }
        (directory / META_FILE).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, directory: Path) -> Self:
        meta = json.loads((directory / META_FILE).read_text(encoding="utf-8"))
        if meta.get("format") != FORMAT_VERSION:
            raise ValueError(f"Unsupported index format {meta.get('format')!r}")
        vectors = np.load(directory / VECTORS_FILE)
        if vectors.shape != (len(meta["ids"]), meta["dimension"]):
            raise ValueError("The index files do not match: rebuild the index with `make index`")
        return cls(meta["ids"], vectors, meta["model_id"])
