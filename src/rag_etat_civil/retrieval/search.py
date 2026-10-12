"""Try the search from the command line.

    make search q="dans quel délai déclarer une naissance ?"

Shows the passages the retriever would give to the answer step, with the page of the
official PDF where each article can be checked.
"""

from __future__ import annotations

import argparse
import textwrap
from collections.abc import Sequence

from rag_etat_civil.config import Settings
from rag_etat_civil.ingestion.build import load_articles
from rag_etat_civil.ingestion.models import Article
from rag_etat_civil.retrieval.factory import IndexNotBuiltError, load_retriever
from rag_etat_civil.retrieval.retriever import RetrievalHit

SNIPPET_CHARS = 300


def format_hit(rank: int, hit: RetrievalHit, article: Article) -> str:
    chunk = hit.chunk
    part = f" (part {chunk.part}/{chunk.total})" if chunk.total > 1 else ""
    header = (
        f"{rank}. Article {chunk.article}{part}  [{' + '.join(hit.sources)}]  "
        f"score {hit.score:.4f}  PDF p. {article.page_start}"
    )
    where = " > ".join(article.breadcrumb)
    text = " ".join(chunk.text.split())
    if len(text) > SNIPPET_CHARS:
        text = text[:SNIPPET_CHARS].rstrip() + "..."
    body = textwrap.fill(text, width=96, initial_indent="   ", subsequent_indent="   ")
    return f"{header}\n   {where}\n{body}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search the law from the command line.")
    parser.add_argument("question", nargs="+", help="the question, in French")
    parser.add_argument("-k", type=int, help="number of passages (default: RETRIEVAL_TOP_K)")
    args = parser.parse_args(argv)
    question = " ".join(args.question)

    settings = Settings.from_env()
    try:
        retriever = load_retriever(settings)
    except IndexNotBuiltError as error:
        print(error)
        return 1

    articles = {a.number: a for a in load_articles(settings.data_dir)}
    hits = retriever.retrieve(question, top_k=args.k)
    print(f"Question: {question}\n")
    if not hits:
        print("No passage found.")
    for rank, hit in enumerate(hits, start=1):
        print(format_hit(rank, hit, articles[hit.chunk.article]), end="\n\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
