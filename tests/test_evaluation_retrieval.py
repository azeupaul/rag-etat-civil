from pathlib import Path

import pytest

from rag_etat_civil.evaluation.dataset import EvalQuestion, load_questions
from rag_etat_civil.evaluation.retrieval import (
    QuestionRetrieval,
    analyse_similarity,
    evaluate_retrieval,
    recommend_top_k,
    score_passages,
)
from rag_etat_civil.evaluation.retrieval_report import render_retrieval_report
from rag_etat_civil.ingestion.build import load_chunks
from rag_etat_civil.ingestion.models import Chunk
from rag_etat_civil.retrieval.numpy_index import NumpyIndex
from rag_etat_civil.retrieval.retriever import HybridRetriever, RetrievalHit
from tests.fakes import HashingEmbedder

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def question(**changes) -> EvalQuestion:
    base = {
        "id": "qx",
        "category": "direct",
        "question": "Une question ?",
        "expected_status": "answered",
        "expected_articles": [10, 12, 13],
        "also_accepted_articles": [],
        "facts": [],
        "forbidden_patterns": [],
        "reference_answer": "Une réponse.",
        "note": None,
    }
    return EvalQuestion.model_validate(base | changes)


def hit(article: int, part: int = 1, similarity: float | None = 0.9, sources=("vector",)):
    chunk = Chunk(f"art-{article:03d}-{part}", article, part, 2, "texte", "texte indexé")
    return RetrievalHit(chunk, 0.03, sources, similarity)


class StubRetriever:
    """Returns a prepared list of article numbers, cut to top_k."""

    def __init__(self, articles: list[int], similarity: float = 0.9) -> None:
        self._articles = articles
        self._similarity = similarity

    def retrieve(self, text: str, top_k: int | None = None) -> list[RetrievalHit]:
        return [hit(a, similarity=self._similarity) for a in self._articles[:top_k]]


def test_scores_count_found_and_missing_articles():
    score = score_passages(question(), [hit(10), hit(11), hit(13)], k=5)

    assert score.found == (10, 13)
    assert score.missing == (12,)
    assert score.hit is True
    assert score.complete is False
    assert score.first_rank == 1


def test_first_rank_is_the_position_of_the_first_expected_article():
    score = score_passages(question(), [hit(40), hit(41), hit(12)], k=5)

    assert score.first_rank == 3


def test_a_question_to_refuse_has_no_hit_or_recall():
    q = question(expected_status="refused", expected_articles=[])

    score = score_passages(q, [hit(10)], k=5)

    assert score.hit is None
    assert score.complete is None
    assert score.first_rank is None


def test_the_articles_of_the_passages_are_distinct_and_ordered():
    score = score_passages(question(), [hit(10, 1), hit(10, 2), hit(12)], k=5)

    assert score.articles == (10, 12)


def test_recommended_top_k_is_the_smallest_that_completes_every_cascade():
    q = question(category="cascade")
    # Article 13 only arrives at the 4th place.
    results = evaluate_retrieval([q], StubRetriever([10, 12, 40, 13]), ks=[2, 3, 4, 6])

    assert recommend_top_k(results) == 4


def test_no_recommendation_when_no_k_is_enough():
    results = evaluate_retrieval(
        [question(category="cascade")], StubRetriever([10, 12]), ks=[1, 2, 5]
    )

    assert recommend_top_k(results) is None


def test_no_recommendation_without_cascade_questions():
    results = evaluate_retrieval([question(category="direct")], StubRetriever([10]), ks=[5])

    assert recommend_top_k(results) is None


def test_invalid_top_k_values_are_rejected():
    with pytest.raises(ValueError, match="positive"):
        evaluate_retrieval([question()], StubRetriever([10]), ks=[0, 5])
    with pytest.raises(ValueError, match="positive"):
        evaluate_retrieval([question()], StubRetriever([10]), ks=[])


def test_best_similarity_is_the_highest_among_the_passages():
    retriever = StubRetriever([10])
    retriever.retrieve = lambda text, top_k=None: [hit(10, similarity=0.8), hit(12, similarity=0.9)]

    (result,) = evaluate_retrieval([question()], retriever, ks=[5])

    assert result.best_similarity == 0.9
    assert result.named is False


def similarity_results(answerable: float, refused: float) -> list[QuestionRetrieval]:
    return [
        evaluate_retrieval([question(id="in")], StubRetriever([10], answerable), ks=[5])[0],
        evaluate_retrieval(
            [question(id="out", expected_status="refused", expected_articles=[])],
            StubRetriever([10], refused),
            ks=[5],
        )[0],
    ]


def test_a_threshold_is_proposed_when_the_groups_are_separated():
    analysis = analyse_similarity(similarity_results(answerable=0.88, refused=0.80))

    assert analysis.lowest_answerable.id == "in"
    assert analysis.highest_refused.id == "out"
    assert analysis.threshold == 0.84


def test_no_threshold_when_the_groups_overlap():
    analysis = analyse_similarity(similarity_results(answerable=0.80, refused=0.85))

    assert analysis.threshold is None


def test_questions_naming_an_article_are_left_out_of_the_threshold():
    chunks = load_chunks(DATA_DIR)
    embedder = HashingEmbedder()
    index = NumpyIndex(
        [c.id for c in chunks],
        embedder.embed_documents([c.indexed_text for c in chunks]),
        embedder.model_id,
    )
    retriever = HybridRetriever(chunks, embedder, index)
    q = question(id="named", question="Que dit l'article 100 ?", expected_articles=[100])

    (result,) = evaluate_retrieval([q], retriever, ks=[5])

    assert result.named is True
    assert all(s.complete for s in result.scores.values())
    assert analyse_similarity([result]).lowest_answerable is None


def test_the_report_covers_the_whole_dataset():
    chunks = load_chunks(DATA_DIR)
    embedder = HashingEmbedder()
    index = NumpyIndex(
        [c.id for c in chunks],
        embedder.embed_documents([c.indexed_text for c in chunks]),
        embedder.model_id,
    )
    retriever = HybridRetriever(chunks, embedder, index)
    questions = load_questions()

    results = evaluate_retrieval(questions, retriever, ks=[5, 10])
    report = render_retrieval_report(results, embedding_model="fake", candidates=20)

    assert report.startswith("# Évaluation de la recherche")
    for q in questions:
        assert f"| {q.id} |" in report
    assert "k=5" in report
    assert "k=10" in report
    assert "MIN_SIMILARITY" in report or "se chevauchent" in report


def test_the_report_names_the_recommended_top_k():
    results = evaluate_retrieval(
        [question(category="cascade")], StubRetriever([10, 12, 13]), ks=[2, 3, 5]
    )

    report = render_retrieval_report(results, embedding_model="fake", candidates=20)

    assert "top_k recommandé : 3" in report
