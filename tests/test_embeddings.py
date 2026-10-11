import numpy as np
import pytest

from rag_etat_civil.config import Settings
from rag_etat_civil.embeddings.base import Embedder
from rag_etat_civil.embeddings.fastembed_embedder import FastEmbedEmbedder
from rag_etat_civil.embeddings.registry import create_embedder
from tests.fakes import HashingEmbedder


class RecordingModel:
    """Stands in for fastembed's TextEmbedding: records the texts it receives."""

    def __init__(self, dimension: int = 4) -> None:
        self.received: list[str] = []
        self.dimension = dimension

    def embed(self, texts):
        for text in texts:
            self.received.append(text)
            yield np.full(self.dimension, 3.0, dtype=np.float32)  # deliberately not normalized


def embedder_with_recording_model(model_name: str) -> tuple[FastEmbedEmbedder, RecordingModel]:
    embedder = FastEmbedEmbedder(model_name)
    model = RecordingModel(embedder.dimension)
    embedder._model = model  # avoids downloading the real model
    return embedder, model


def test_e5_prefixes_are_added():
    embedder, model = embedder_with_recording_model("intfloat/multilingual-e5-large")
    embedder.embed_documents(["Article 10"])
    embedder.embed_query("délai de déclaration ?")
    assert model.received == ["passage: Article 10", "query: délai de déclaration ?"]


def test_no_prefix_for_other_models():
    embedder, model = embedder_with_recording_model(
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    embedder.embed_query("bonjour")
    assert model.received == ["bonjour"]


def test_vectors_are_normalized_float32():
    embedder, _ = embedder_with_recording_model("intfloat/multilingual-e5-large")
    vectors = embedder.embed_documents(["a", "b"])
    assert vectors.shape == (2, 1024)
    assert vectors.dtype == np.float32
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)
    assert embedder.embed_query("a").shape == (1024,)


def test_model_is_not_loaded_at_construction():
    assert FastEmbedEmbedder()._model is None


def test_unsupported_model_is_rejected_with_a_helpful_message():
    with pytest.raises(ValueError, match="not supported by fastembed"):
        FastEmbedEmbedder("BAAI/bge-m3")


def test_model_id_and_dimension():
    embedder = FastEmbedEmbedder()
    assert embedder.model_id == "fastembed:intfloat/multilingual-e5-large"
    assert embedder.dimension == 1024


def test_registry_builds_the_configured_embedder():
    assert isinstance(create_embedder(Settings()), FastEmbedEmbedder)


def test_registry_rejects_unknown_embedder():
    with pytest.raises(ValueError, match="Unknown EMBEDDER 'nope'"):
        create_embedder(Settings(embedder="nope"))


def test_hashing_embedder_respects_the_contract():
    embedder: Embedder = HashingEmbedder()
    docs = embedder.embed_documents(["la naissance est déclarée", "le décès est déclaré"])
    assert docs.shape == (2, embedder.dimension)
    assert np.allclose(np.linalg.norm(docs, axis=1), 1.0)
    query = embedder.embed_query("naissance")
    assert query.shape == (embedder.dimension,)
    assert float(docs[0] @ query) > float(docs[1] @ query)


@pytest.mark.model
def test_real_model_prefers_the_relevant_passage():
    """Needs the real model (about 2.2 GB, downloaded once): run `make test-model`."""
    settings = Settings()
    embedder = create_embedder(settings)
    passages = [
        "La naissance est déclarée à l'officier d'état civil dans un délai de quatre-vingt-dix "
        "(90) jours suivant l'accouchement.",
        "Le décès est déclaré à l'officier d'état civil du lieu du décès.",
        "Les frais de fonctionnement du système national de l'état civil sont financés par l'État.",
    ]
    vectors = embedder.embed_documents(passages)
    assert vectors.shape == (3, embedder.dimension)
    scores = vectors @ embedder.embed_query("Dans quel délai faut-il déclarer une naissance ?")
    assert int(np.argmax(scores)) == 0, scores
