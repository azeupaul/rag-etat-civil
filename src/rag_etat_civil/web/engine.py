"""What the web routes need from the rest of the application, loaded once and reused.

Loading the embedding model takes several seconds, so it must not happen at each question.
Everything is loaded on first use (or at startup with `preload`) and then kept. A failed load
is not kept: the next request tries again, so fixing the problem needs no restart.
"""

from __future__ import annotations

import threading

from rag_etat_civil.answering.answerer import Answerer
from rag_etat_civil.answering.factory import load_answerer
from rag_etat_civil.config import Settings
from rag_etat_civil.ingestion.build import load_articles
from rag_etat_civil.ingestion.models import Article
from rag_etat_civil.retrieval.numpy_index import META_FILE


class EngineUnavailable(RuntimeError):
    """The data, the index or the language model setup is missing or wrong."""


class Engine:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._answerer: Answerer | None = None
        self._articles: dict[int, Article] | None = None

    def index_ready(self) -> bool:
        return (self._settings.index_dir / META_FILE).exists()

    def articles(self) -> dict[int, Article]:
        with self._lock:
            if self._articles is None:
                try:
                    loaded = load_articles(self._settings.data_dir)
                except FileNotFoundError as error:
                    raise EngineUnavailable("No articles found: run `make ingest`.") from error
                self._articles = {article.number: article for article in loaded}
            return self._articles

    def answerer(self) -> Answerer:
        with self._lock:
            if self._answerer is None:
                try:
                    self._answerer = load_answerer(self._settings)
                except (FileNotFoundError, ValueError) as error:
                    # Missing index, unknown provider or missing API key.
                    raise EngineUnavailable(str(error)) from error
            return self._answerer

    def preload(self) -> None:
        """Load everything now, so that the first visitor does not wait for the model."""
        self.articles()
        self.answerer()
