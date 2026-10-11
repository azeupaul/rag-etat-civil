"""Split articles into chunks to index.

Rule: one article = one chunk, so that every chunk maps to exactly one citable article.
Only very long articles (in practice article 3, which lists the definitions) are cut, between
two lines (paragraphs or definitions). Every part keeps the same article number.
"""

from __future__ import annotations

from rag_etat_civil.ingestion.models import Article, Chunk

MAX_ARTICLE_CHARS = 2500  # above this length, an article is cut into several chunks
TARGET_PART_CHARS = 800  # approximate size of each part of a cut article


def context(article: Article) -> str:
    """Position of the article in the structure of the law, as plain text."""
    divisions = (article.chapter, article.section, article.paragraph)
    return " > ".join(d.title.capitalize() for d in divisions if d)


def pack_lines(text: str, target: int) -> list[str]:
    """Group whole lines into blocks of roughly `target` characters."""
    blocks: list[list[str]] = [[]]
    size = 0
    for line in text.splitlines():
        if blocks[-1] and size + len(line) > target:
            blocks.append([])
            size = 0
        blocks[-1].append(line)
        size += len(line) + 1
    return ["\n".join(block) for block in blocks]


def chunk_article(article: Article) -> list[Chunk]:
    if len(article.text) <= MAX_ARTICLE_CHARS:
        parts = [article.text]
    else:
        parts = pack_lines(article.text, TARGET_PART_CHARS)

    chunks = []
    for index, text in enumerate(parts, start=1):
        suffix = f"-{index}" if len(parts) > 1 else ""
        # The context is in French on purpose: it is matched against French questions.
        heading = f"Article {article.number}"
        if len(parts) > 1:
            heading += f" (partie {index}/{len(parts)})"
        chunks.append(
            Chunk(
                id=f"art-{article.number:03d}{suffix}",
                article=article.number,
                part=index,
                total=len(parts),
                text=text,
                indexed_text=f"Loi n° 2024/016. {context(article)}. {heading}. {text}",
            )
        )
    return chunks


def chunk_articles(articles: list[Article]) -> list[Chunk]:
    return [chunk for article in articles for chunk in chunk_article(article)]
