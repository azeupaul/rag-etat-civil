"""Build the files derived from the text of the law.

    uv run python -m rag_etat_civil.ingestion.build

Input:   data/raw/loi_2024_016.txt
Outputs: data/processed/articles.json   (the 130 articles and their place in the structure)
         data/processed/chunks.jsonl    (chunks to index, one per line)
"""

from __future__ import annotations

import json
from pathlib import Path

from rag_etat_civil.config import Settings
from rag_etat_civil.ingestion.chunking import chunk_articles
from rag_etat_civil.ingestion.models import Article, Chunk
from rag_etat_civil.ingestion.parser import parse_file

RAW_PATH = "raw/loi_2024_016.txt"
ARTICLES_PATH = "processed/articles.json"
CHUNKS_PATH = "processed/chunks.jsonl"


def render_articles(articles: list[Article]) -> str:
    return json.dumps([a.to_dict() for a in articles], ensure_ascii=False, indent=2) + "\n"


def render_chunks(chunks: list[Chunk]) -> str:
    return "".join(json.dumps(c.to_dict(), ensure_ascii=False) + "\n" for c in chunks)


def build(data_dir: Path) -> tuple[list[Article], list[Chunk]]:
    articles = parse_file(data_dir / RAW_PATH)
    chunks = chunk_articles(articles)
    (data_dir / "processed").mkdir(exist_ok=True)
    (data_dir / ARTICLES_PATH).write_text(render_articles(articles), encoding="utf-8")
    (data_dir / CHUNKS_PATH).write_text(render_chunks(chunks), encoding="utf-8")
    return articles, chunks


def load_articles(data_dir: Path) -> list[Article]:
    raw = json.loads((data_dir / ARTICLES_PATH).read_text(encoding="utf-8"))
    return [Article.from_dict(item) for item in raw]


def load_chunks(data_dir: Path) -> list[Chunk]:
    lines = (data_dir / CHUNKS_PATH).read_text(encoding="utf-8").splitlines()
    return [Chunk.from_dict(json.loads(line)) for line in lines if line]


def main() -> None:
    data_dir = Settings.from_env().data_dir
    articles, chunks = build(data_dir)
    print(f"{len(articles)} articles, {len(chunks)} chunks written to {data_dir / 'processed'}")


if __name__ == "__main__":
    main()
