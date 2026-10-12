"""Measure whether the retriever brings the expected articles to the language model.

The retrieval step is judged alone, before any language model is involved: if an expected
article is not among the passages, no prompt can make the model cite it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from rag_etat_civil.evaluation.dataset import EvalQuestion
from rag_etat_civil.retrieval.retriever import HybridRetriever, RetrievalHit


@dataclass(frozen=True, slots=True)
class KScore:
    """What the retriever returned for one question with one value of top_k."""

    k: int
    articles: tuple[int, ...]  # distinct articles among the passages, best first
    expected: tuple[int, ...]  # articles an ideal answer relies on
    first_rank: int | None  # position (1 = best) of the first passage of an expected article

    @property
    def found(self) -> tuple[int, ...]:
        return tuple(a for a in self.expected if a in self.articles)

    @property
    def missing(self) -> tuple[int, ...]:
        return tuple(a for a in self.expected if a not in self.articles)

    @property
    def hit(self) -> bool | None:
        """At least one expected article is there. None when no article is expected."""
        return bool(self.found) if self.expected else None

    @property
    def complete(self) -> bool | None:
        """Every expected article is there. None when no article is expected."""
        return not self.missing if self.expected else None


@dataclass(frozen=True, slots=True)
class QuestionRetrieval:
    question: EvalQuestion
    scores: dict[int, KScore]  # by value of top_k
    best_similarity: float | None  # best cosine similarity among the passages
    named: bool  # the question names an article: the similarity threshold never applies


def score_passages(question: EvalQuestion, hits: Sequence[RetrievalHit], k: int) -> KScore:
    expected = set(question.expected_articles)
    first_rank = next(
        (rank for rank, hit in enumerate(hits, start=1) if hit.chunk.article in expected), None
    )
    articles = tuple(dict.fromkeys(hit.chunk.article for hit in hits))
    return KScore(k, articles, tuple(question.expected_articles), first_rank)


def evaluate_retrieval(
    questions: Sequence[EvalQuestion], retriever: HybridRetriever, ks: Sequence[int]
) -> list[QuestionRetrieval]:
    """Run every question for every top_k.

    The retriever is called once per value of k rather than cut from one long list: articles
    named in the question are never cut, so the lists for different k are not simple prefixes.
    """
    ks = sorted(set(ks))
    if not ks or ks[0] < 1:
        raise ValueError("top_k values must be positive integers")
    results = []
    for question in questions:
        hits_by_k = {k: retriever.retrieve(question.question, top_k=k) for k in ks}
        widest = hits_by_k[ks[-1]]
        similarities = [hit.similarity for hit in widest if hit.similarity is not None]
        results.append(
            QuestionRetrieval(
                question=question,
                scores={k: score_passages(question, hits, k) for k, hits in hits_by_k.items()},
                best_similarity=max(similarities, default=None),
                named=any("lookup" in hit.sources for hit in widest),
            )
        )
    return results


def recommend_top_k(results: Sequence[QuestionRetrieval], category: str = "cascade") -> int | None:
    """The smallest top_k for which every question of the category gets all its articles.

    A smaller k means fewer tokens and less noise for the model, so it wins when it is enough.
    """
    cascades = [r for r in results if r.question.category == category]
    if not cascades:
        return None
    for k in sorted(cascades[0].scores):
        if all(r.scores[k].complete for r in cascades):
            return k
    return None


# The threshold is a cheap filter for questions that have nothing to do with the law. Questions
# close to civil status that the law does not answer ("out_of_law") cannot be told apart from
# legitimate ones by a number: they are left to the language model.
THRESHOLD_REFUSED_CATEGORIES = ("off_topic", "adversarial")
FRAGILE_MARGIN = 0.03


@dataclass(frozen=True, slots=True)
class ScoredQuestion:
    id: str
    similarity: float


@dataclass(frozen=True, slots=True)
class SimilarityAnalysis:
    """Can a similarity threshold tell the questions the law answers from off-topic ones?"""

    lowest_answerable: ScoredQuestion | None  # the answerable question that scores lowest
    highest_off_topic: ScoredQuestion | None  # the off-topic question that scores highest
    threshold: float | None  # None when the two groups overlap (or one is empty)
    left_to_model: tuple[ScoredQuestion, ...]  # refused questions a threshold cannot judge

    @property
    def margin(self) -> float | None:
        """The gap between the two groups: how wrong a new question can be before it fails."""
        if self.lowest_answerable is None or self.highest_off_topic is None:
            return None
        return self.lowest_answerable.similarity - self.highest_off_topic.similarity

    @property
    def is_fragile(self) -> bool:
        return self.margin is not None and self.margin < FRAGILE_MARGIN


def analyse_similarity(
    results: Sequence[QuestionRetrieval],
    off_topic_categories: Sequence[str] = THRESHOLD_REFUSED_CATEGORIES,
) -> SimilarityAnalysis:
    """Questions naming an article are left out: the threshold never applies to them."""
    scored = [
        (r.question, ScoredQuestion(r.question.id, r.best_similarity))
        for r in results
        if not r.named and r.best_similarity is not None
    ]
    answerable = [s for q, s in scored if q.expected_status == "answered"]
    off_topic = [
        s
        for q, s in scored
        if q.expected_status == "refused" and q.category in off_topic_categories
    ]
    left_to_model = tuple(
        s
        for q, s in scored
        if q.expected_status == "refused" and q.category not in off_topic_categories
    )
    low = min(answerable, key=lambda q: q.similarity, default=None)
    high = max(off_topic, key=lambda q: q.similarity, default=None)
    threshold = None
    if low and high and low.similarity > high.similarity:
        threshold = round((low.similarity + high.similarity) / 2, 3)
    return SimilarityAnalysis(low, high, threshold, left_to_model)
