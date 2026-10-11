"""Split the text of the law into articles, keeping chapter, section and paragraph."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from rag_etat_civil.ingestion.models import Article, Division

PAGE_RE = re.compile(r"^\[\[p\.(\d+)\]\]$")
ARTICLE_RE = re.compile(r"^ARTICLE (\d+)(?:er)?\.-\s*(.*)$")
# "PARAGRA\w+" also accepts the typo "PARAGRAGRHE", kept as-is in the official text.
DIVISION_RE = re.compile(r"^(CHAPITRE|SECTION|PARAGRA\w+)\s+([IVX]+)$")
SIGNATURE_RE = re.compile(r"^Yaound[ée], le ")

# Depth of each kind of division. Anything that is not a chapter or a section is a paragraph.
_CHAPTER, _SECTION, _PARAGRAPH = 0, 1, 2
_LEVELS = {"CHAPITRE": _CHAPTER, "SECTION": _SECTION}


class ParseError(ValueError):
    """The text does not have the expected format."""


@dataclass(slots=True)
class _OpenArticle:
    """An article being read: collects its lines until the next heading."""

    number: int
    lines: list[str]
    page_start: int
    page_end: int
    divisions: tuple[Division | None, ...]

    def to_article(self) -> Article:
        chapter, section, paragraph = self.divisions
        return Article(
            number=self.number,
            text="\n".join(self.lines).strip(),
            page_start=self.page_start,
            page_end=self.page_end,
            chapter=chapter,
            section=section,
            paragraph=paragraph,
        )


def parse_law(text: str) -> list[Article]:
    """Turn the transcription of the law into an ordered list of articles."""
    lines = text.splitlines()
    articles: list[Article] = []

    # Division currently in force at each level: [chapter, section, paragraph].
    divisions: list[Division | None] = [None, None, None]
    page = 1
    current: _OpenArticle | None = None
    i = 0

    def close_current() -> None:
        nonlocal current
        if current is not None:
            articles.append(current.to_article())
            current = None

    while i < len(lines):
        line = lines[i].rstrip()
        i += 1

        if SIGNATURE_RE.match(line):  # end of the law: what follows is not part of an article
            break

        if match := PAGE_RE.match(line):
            page = int(match.group(1))
            if current is not None:
                current.page_end = page
            continue

        if match := DIVISION_RE.match(line):
            close_current()
            level = _LEVELS.get(match.group(1), _PARAGRAPH)
            # The title can span several lines: read until the next blank line.
            title_lines = []
            while i < len(lines) and lines[i].strip():
                title_lines.append(lines[i].strip())
                i += 1
            divisions[level] = Division(match.group(2), " ".join(title_lines))
            # A new chapter resets the section and paragraph; a new section resets the paragraph.
            for lower in range(level + 1, _PARAGRAPH + 1):
                divisions[lower] = None
            continue

        if match := ARTICLE_RE.match(line):
            close_current()
            first_line = match.group(2)
            current = _OpenArticle(
                number=int(match.group(1)),
                lines=[first_line] if first_line else [],
                page_start=page,
                page_end=page,
                divisions=tuple(divisions),
            )
            continue

        if current is not None:
            current.lines.append(line)

    close_current()
    _check(articles)
    return articles


def _check(articles: list[Article]) -> None:
    """Fail loudly if the result is not what the law looks like (1..N, none empty)."""
    numbers = [a.number for a in articles]
    if numbers != list(range(1, len(numbers) + 1)):
        raise ParseError(f"Article numbers are not consecutive: {numbers}")
    for article in articles:
        if not article.text:
            raise ParseError(f"Article {article.number} is empty")


def parse_file(path: Path) -> list[Article]:
    return parse_law(path.read_text(encoding="utf-8"))
