"""Assemble a ready-to-use answerer from the files on disk and the settings."""

from __future__ import annotations

from rag_etat_civil.answering.answerer import Answerer
from rag_etat_civil.config import Settings
from rag_etat_civil.ingestion.build import load_articles
from rag_etat_civil.llm.registry import create_llm
from rag_etat_civil.retrieval.factory import load_retriever


def load_answerer(settings: Settings) -> Answerer:
    """Raises `IndexNotBuiltError` without an index and `ValueError` for a wrong LLM setup."""
    return Answerer(
        load_retriever(settings),
        create_llm(settings),
        load_articles(settings.data_dir),
        min_similarity=settings.min_similarity,
    )
