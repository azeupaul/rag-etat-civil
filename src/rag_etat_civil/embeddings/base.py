"""The contract every embedding model must respect."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

Vectors = NDArray[np.float32]


class Embedder(ABC):
    """Turns text into vectors.

    Rules shared by all implementations:
    - vectors are float32 and L2-normalized, so a dot product is a cosine similarity;
    - passages and questions are embedded by two different methods, because some models
      need to be told which is which (the e5 family does).
    """

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Unique name of the model, stored with the index (e.g. "fastembed:org/model")."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Length of the vectors produced."""

    @abstractmethod
    def embed_documents(self, texts: Sequence[str]) -> Vectors:
        """Embed passages of the law. Returns an array of shape (len(texts), dimension)."""

    @abstractmethod
    def embed_query(self, text: str) -> Vectors:
        """Embed a user question. Returns an array of shape (dimension,)."""
