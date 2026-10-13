"""The typed shapes the web routes receive and return (also the JSON contract of the API)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from rag_etat_civil.ingestion.models import Article


class AskRequest(BaseModel):
    """Body of `POST /api/ask`."""

    question: str


class ArticleView(BaseModel):
    """An article of the law, as returned by `GET /api/articles/{number}`."""

    number: int
    text: str  # exact text of the article
    page_start: int  # pages of the official PDF
    page_end: int
    breadcrumb: list[str]  # chapter, section and paragraph the article belongs to

    @classmethod
    def from_article(cls, article: Article) -> ArticleView:
        return cls(
            number=article.number,
            text=article.text,
            page_start=article.page_start,
            page_end=article.page_end,
            breadcrumb=article.breadcrumb,
        )


class HealthStatus(BaseModel):
    """Body of `GET /health`. It never calls the language model, so it costs nothing."""

    status: Literal["ok", "degraded"]  # degraded: the data or the index is missing
    version: str
    index_ready: bool
    articles: int


class ErrorResponse(BaseModel):
    error: str
