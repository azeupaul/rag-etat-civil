from pathlib import Path

import pytest

from rag_etat_civil.ingestion.build import load_chunks
from rag_etat_civil.ingestion.models import Chunk
from rag_etat_civil.retrieval.numpy_index import NumpyIndex
from rag_etat_civil.retrieval.retriever import HybridRetriever
from rag_etat_civil.retrieval.vector_index import IndexMismatchError
from tests.fakes import HashingEmbedder

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def build_index(chunks: list[Chunk], embedder: HashingEmbedder) -> NumpyIndex:
    vectors = embedder.embed_documents([c.indexed_text for c in chunks])
    return NumpyIndex([c.id for c in chunks], vectors, embedder.model_id)


@pytest.fixture(scope="module")
def chunks():
    return load_chunks(DATA_DIR)


@pytest.fixture(scope="module")
def retriever(chunks):
    embedder = HashingEmbedder()
    return HybridRetriever(chunks, embedder, build_index(chunks, embedder))


def ids(hits):
    return [hit.chunk.id for hit in hits]


def test_named_article_comes_first(retriever):
    hits = retriever.retrieve("Que dit l'article 36 ?")
    assert hits[0].chunk.id == "art-036"
    assert "lookup" in hits[0].sources
    assert len(hits) == 5


def test_named_articles_come_before_search_results(retriever):
    hits = retriever.retrieve("Comparez les articles 10 et 22")
    assert ids(hits)[:2] == ["art-010", "art-022"]
    assert all("lookup" in hit.sources for hit in hits[:2])
    assert all("lookup" not in hit.sources for hit in hits[2:])


def test_every_part_of_a_long_article_is_returned(retriever):
    hits = retriever.retrieve("Que dit l'article 3 ?")
    parts = [h.chunk for h in hits if h.chunk.article == 3]
    assert len(parts) == parts[0].total == 10
    assert len(hits) == 10  # named articles are never cut to top_k


def test_unknown_article_number_is_ignored(retriever):
    hits = retriever.retrieve("Que dit l'article 500 ?")
    assert all("lookup" not in hit.sources for hit in hits)


def test_birth_declaration_delay_is_in_the_results(retriever):
    assert "art-010" in ids(retriever.retrieve("Dans quel délai déclarer une naissance ?"))


def test_passage_found_by_two_methods_lists_both_sources(retriever):
    hit = next(h for h in retriever.retrieve("90 jours naissance") if h.chunk.id == "art-010")
    assert {"vector", "bm25"} <= set(hit.sources)


def test_top_k_is_respected_and_can_be_overridden(retriever):
    question = "Qui peut reconnaître un enfant né hors mariage ?"
    assert len(retriever.retrieve(question)) == 5
    assert len(retriever.retrieve(question, top_k=2)) == 2
    assert len(retriever.retrieve(question, top_k=8)) == 8


def test_scores_are_sorted_among_search_results(retriever):
    scores = [h.score for h in retriever.retrieve("jugement supplétif")]
    assert scores == sorted(scores, reverse=True)


def test_empty_question_gives_no_results(retriever):
    assert retriever.retrieve("") == []
    assert retriever.retrieve("   ") == []


def test_results_are_reproducible(retriever):
    question = "sanctions pour faux acte"
    assert retriever.retrieve(question) == retriever.retrieve(question)


def test_index_built_with_another_model_is_refused(chunks):
    other = HashingEmbedder(dimension=64)
    with pytest.raises(IndexMismatchError, match="make index"):
        HybridRetriever(chunks, HashingEmbedder(), build_index(chunks, other))


def test_index_with_a_different_number_of_chunks_is_refused(chunks):
    embedder = HashingEmbedder()
    with pytest.raises(IndexMismatchError, match="Rebuild"):
        HybridRetriever(chunks, embedder, build_index(chunks[:-1], embedder))


def test_index_with_unknown_chunk_ids_is_detected(chunks):
    embedder = HashingEmbedder()
    renamed = [
        Chunk(f"x-{c.id}", c.article, c.part, c.total, c.text, c.indexed_text) for c in chunks
    ]
    retriever = HybridRetriever(chunks, embedder, build_index(renamed, embedder))
    with pytest.raises(IndexMismatchError, match="unknown chunk"):
        retriever.retrieve("naissance")
