import numpy as np
import pytest

from rag_etat_civil.retrieval.numpy_index import NumpyIndex
from rag_etat_civil.retrieval.vector_index import IndexMismatchError, Match
from tests.fakes import HashingEmbedder

TEXTS = {
    "birth": "la naissance est déclarée à l'officier d'état civil",
    "death": "le décès est déclaré à l'officier d'état civil",
    "funding": "le financement du système national est assuré par l'État",
}


@pytest.fixture
def embedder():
    return HashingEmbedder()


@pytest.fixture
def index(embedder):
    vectors = embedder.embed_documents(list(TEXTS.values()))
    return NumpyIndex(list(TEXTS), vectors, embedder.model_id)


def test_nearest_chunk_comes_first(index, embedder):
    matches = index.search(embedder.embed_query("déclarer une naissance"), k=3)
    assert matches[0].id == "birth"
    assert [m.score for m in matches] == sorted((m.score for m in matches), reverse=True)


def test_k_limits_the_results_and_larger_k_returns_everything(index, embedder):
    query = embedder.embed_query("décès")
    assert len(index.search(query, k=2)) == 2
    assert len(index.search(query, k=50)) == 3


def test_identical_text_has_a_score_of_one(index, embedder):
    match = index.search(embedder.embed_query(TEXTS["funding"]), k=1)[0]
    assert match.id == "funding"
    assert match.score == pytest.approx(1.0, abs=1e-5)


def test_ties_keep_the_original_order(embedder):
    vector = embedder.embed_query("même texte")
    index = NumpyIndex(["a", "b", "c"], np.vstack([vector, vector, vector]), embedder.model_id)
    assert [m.id for m in index.search(vector, k=3)] == ["a", "b", "c"]


def test_save_then_load_gives_the_same_results(index, embedder, tmp_path):
    index.save(tmp_path / "index")
    loaded = NumpyIndex.load(tmp_path / "index")
    query = embedder.embed_query("naissance")
    assert loaded.search(query, k=3) == index.search(query, k=3)
    assert (loaded.model_id, loaded.dimension, len(loaded)) == (
        embedder.model_id,
        embedder.dimension,
        3,
    )


def test_search_returns_matches(index, embedder):
    assert isinstance(index.search(embedder.embed_query("naissance"), k=1)[0], Match)


def test_ids_and_vectors_must_line_up(embedder):
    vectors = embedder.embed_documents(["a", "b"])
    with pytest.raises(ValueError, match="one vector per id"):
        NumpyIndex(["only-one"], vectors, embedder.model_id)
    with pytest.raises(ValueError, match="unique"):
        NumpyIndex(["x", "x"], vectors, embedder.model_id)


def test_query_of_the_wrong_size_is_rejected(index):
    with pytest.raises(ValueError, match="query of shape"):
        index.search(np.zeros(3, dtype=np.float32), k=1)


def test_compatible_with_the_model_that_built_it(index, embedder):
    index.check_compatible(embedder)  # does not raise


def test_incompatible_model_is_refused_with_a_clear_message(index):
    other = HashingEmbedder(dimension=64)
    with pytest.raises(IndexMismatchError, match="make index"):
        index.check_compatible(other)


def test_corrupted_files_are_detected(index, tmp_path):
    index.save(tmp_path)
    np.save(tmp_path / "vectors.npy", np.zeros((1, 256), dtype=np.float32))
    with pytest.raises(ValueError, match="do not match"):
        NumpyIndex.load(tmp_path)
