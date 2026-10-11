"""Choose the embedding implementation from the settings (EMBEDDER variable).

To add another provider: write a class that extends `Embedder`, then add one line below.
"""

from __future__ import annotations

from collections.abc import Callable

from rag_etat_civil.config import Settings
from rag_etat_civil.embeddings.base import Embedder
from rag_etat_civil.embeddings.fastembed_embedder import FastEmbedEmbedder

EMBEDDERS: dict[str, Callable[[Settings], Embedder]] = {
    "fastembed": lambda s: FastEmbedEmbedder(s.embedding_model, s.embedding_cache_dir),
}


def create_embedder(settings: Settings) -> Embedder:
    try:
        factory = EMBEDDERS[settings.embedder]
    except KeyError:
        raise ValueError(
            f"Unknown EMBEDDER {settings.embedder!r}. Available: {sorted(EMBEDDERS)}"
        ) from None
    return factory(settings)
