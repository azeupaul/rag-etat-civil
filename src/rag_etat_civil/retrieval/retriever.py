"""The hybrid retriever: from a question to the passages of the law that answer it.

Three sources are combined:
- "lookup": the articles named in the question ("article 36");
- "vector": the passages closest in meaning (embeddings);
- "bm25": the passages sharing the most (and rarest) words with the question.

The vector and BM25 rankings are merged with RRF. Articles named in the question always come
first: when someone asks about article 36, they must get article 36, whatever the search says.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from rag_etat_civil.embeddings.base import Embedder
from rag_etat_civil.ingestion.models import Chunk
from rag_etat_civil.retrieval.bm25 import BM25
from rag_etat_civil.retrieval.fusion import DEFAULT_K, reciprocal_rank_fusion
from rag_etat_civil.retrieval.lookup import find_article_numbers
from rag_etat_civil.retrieval.vector_index import IndexMismatchError, VectorIndex

MAX_LOOKUP_ARTICLES = 5  # a question naming 20 articles is not a question about one of them


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    chunk: Chunk
    score: float  # RRF score: only meaningful to compare hits of the same search
    sources: tuple[str, ...]  # which of "lookup", "vector", "bm25" found this chunk


class HybridRetriever:
    def __init__(
        self,
        chunks: Sequence[Chunk],
        embedder: Embedder,
        index: VectorIndex,
        *,
        candidates: int = 20,
        top_k: int = 5,
        rrf_k: int = DEFAULT_K,
    ) -> None:
        index.check_compatible(embedder)
        if len(index) != len(chunks):
            raise IndexMismatchError(
                f"The index holds {len(index)} vectors but there are {len(chunks)} chunks. "
                "Rebuild the index with `make index`."
            )
        self._chunks = {chunk.id: chunk for chunk in chunks}
        self._by_article: dict[int, list[str]] = {}
        for chunk in chunks:
            self._by_article.setdefault(chunk.article, []).append(chunk.id)
        self._max_article = max(self._by_article, default=0)

        self._embedder = embedder
        self._index = index
        self._bm25 = BM25([c.id for c in chunks], [c.indexed_text for c in chunks])
        self._candidates = candidates
        self._top_k = top_k
        self._rrf_k = rrf_k

    def retrieve(self, question: str, top_k: int | None = None) -> list[RetrievalHit]:
        """Return the best passages for the question, best first."""
        question = question.strip()
        if not question:
            return []
        top_k = self._top_k if top_k is None else top_k

        rankings = {
            "lookup": self._lookup(question),
            "vector": self._vector_search(question),
            "bm25": [m.id for m in self._bm25.search(question, self._candidates)],
        }
        fused = reciprocal_rank_fusion(rankings, k=self._rrf_k)

        named = [f for f in fused if "lookup" in f.sources]
        others = [f for f in fused if "lookup" not in f.sources]
        # Named articles are never cut, even if they take more than top_k places.
        selected = named + others[: max(0, top_k - len(named))]
        return [RetrievalHit(self._chunk(f.id), f.score, f.sources) for f in selected]

    def _lookup(self, question: str) -> list[str]:
        numbers = find_article_numbers(question, self._max_article)[:MAX_LOOKUP_ARTICLES]
        return [chunk_id for number in numbers for chunk_id in self._by_article.get(number, [])]

    def _vector_search(self, question: str) -> list[str]:
        query = self._embedder.embed_query(question)
        return [m.id for m in self._index.search(query, self._candidates)]

    def _chunk(self, chunk_id: str) -> Chunk:
        try:
            return self._chunks[chunk_id]
        except KeyError:
            raise IndexMismatchError(
                f"The index contains an unknown chunk {chunk_id!r}. "
                "Rebuild the index with `make index`."
            ) from None
