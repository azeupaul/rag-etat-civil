"""Embeddings computed locally with fastembed (ONNX runtime, no PyTorch)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from rag_etat_civil.embeddings.base import Embedder, Vectors

if TYPE_CHECKING:
    from fastembed import TextEmbedding

DEFAULT_MODEL = "intfloat/multilingual-e5-large"


def _uses_e5_prefixes(model_name: str) -> bool:
    """e5 models expect "query: " or "passage: " before the text; fastembed does not add them."""
    return "e5" in model_name.split("/")[-1].lower()


def _normalize(vectors: Vectors) -> Vectors:
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return (vectors / np.clip(norms, 1e-12, None)).astype(np.float32)


class FastEmbedEmbedder(Embedder):
    def __init__(self, model_name: str = DEFAULT_MODEL, cache_dir: Path | None = None) -> None:
        from fastembed import TextEmbedding

        supported = {m["model"]: m for m in TextEmbedding.list_supported_models()}
        if model_name not in supported:
            raise ValueError(
                f"Model {model_name!r} is not supported by fastembed. "
                f"Multilingual models available: "
                f"{sorted(name for name in supported if 'multilingual' in name.lower())}"
            )
        self._model_name = model_name
        self._dimension = int(supported[model_name]["dim"])
        self._cache_dir = cache_dir
        self._prefixes = ("query: ", "passage: ") if _uses_e5_prefixes(model_name) else ("", "")
        self._model: TextEmbedding | None = None  # loaded on first use (it may be downloaded)

    @property
    def model_id(self) -> str:
        return f"fastembed:{self._model_name}"

    @property
    def dimension(self) -> int:
        return self._dimension

    def _load(self) -> TextEmbedding:
        if self._model is None:
            from fastembed import TextEmbedding

            cache = str(self._cache_dir) if self._cache_dir else None
            self._model = TextEmbedding(self._model_name, cache_dir=cache)
        return self._model

    def _embed(self, texts: list[str]) -> Vectors:
        vectors = np.vstack(list(self._load().embed(texts)))
        return _normalize(vectors)

    def embed_documents(self, texts: Sequence[str]) -> Vectors:
        prefix = self._prefixes[1]
        return self._embed([prefix + text for text in texts])

    def embed_query(self, text: str) -> Vectors:
        prefix = self._prefixes[0]
        return self._embed([prefix + text])[0]
