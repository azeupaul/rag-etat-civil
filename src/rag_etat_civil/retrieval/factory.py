"""Assemble a ready-to-use retriever from the files on disk and the settings."""

from __future__ import annotations

from rag_etat_civil.config import Settings
from rag_etat_civil.embeddings.base import Embedder
from rag_etat_civil.embeddings.registry import create_embedder
from rag_etat_civil.ingestion.build import load_chunks
from rag_etat_civil.retrieval.numpy_index import META_FILE, NumpyIndex
from rag_etat_civil.retrieval.retriever import HybridRetriever


class IndexNotBuiltError(FileNotFoundError):
    """The index has not been built yet."""


def load_retriever(settings: Settings, embedder: Embedder | None = None) -> HybridRetriever:
    if not (settings.index_dir / META_FILE).exists():
        raise IndexNotBuiltError(
            f"No index found in {settings.index_dir}. Build it with `make index`."
        )
    return HybridRetriever(
        load_chunks(settings.data_dir),
        embedder or create_embedder(settings),
        NumpyIndex.load(settings.index_dir),
        candidates=settings.retrieval_candidates,
        top_k=settings.retrieval_top_k,
    )
