"""Data structures used by the ingestion step (all JSON-serializable)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Division:
    """A division of the law: a chapter, a section or a paragraph."""

    numeral: str  # Roman numeral as written in the law ("II")
    title: str  # title as written in the law (uppercase, no accents)


@dataclass(frozen=True, slots=True)
class Article:
    """One article of the law, with its position in the structure of the text."""

    number: int
    text: str  # exact text of the article, without the "ARTICLE N.-" heading
    page_start: int
    page_end: int
    chapter: Division | None
    section: Division | None
    paragraph: Division | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Article:
        def division(key: str) -> Division | None:
            value = data[key]
            return Division(**value) if value else None

        return cls(
            number=data["number"],
            text=data["text"],
            page_start=data["page_start"],
            page_end=data["page_end"],
            chapter=division("chapter"),
            section=division("section"),
            paragraph=division("paragraph"),
        )

    @property
    def breadcrumb(self) -> list[str]:
        """Human-readable path from the chapter down to the paragraph.

        The labels stay in French because they are the terms used by the law itself.
        """
        levels = (
            ("Chapitre", self.chapter),
            ("Section", self.section),
            ("Paragraphe", self.paragraph),
        )
        return [f"{label} {d.numeral} : {d.title}" for label, d in levels if d is not None]


@dataclass(frozen=True, slots=True)
class Chunk:
    """A passage to index. One article gives one chunk, or several if it is very long."""

    id: str  # "art-009" or "art-003-2"
    article: int
    part: int  # 1..total
    total: int
    text: str  # text that is displayed and cited (exact extract of the article)
    indexed_text: str  # text sent to the embedding model and to BM25 (text + context)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Chunk:
        return cls(**data)
