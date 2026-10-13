import json
import shutil

import pytest

from rag_etat_civil.config import Settings
from rag_etat_civil.embeddings.registry import EMBEDDERS
from rag_etat_civil.ingestion.build import load_chunks
from rag_etat_civil.llm.base import LLMError
from rag_etat_civil.llm.registry import LLM_PROVIDERS
from rag_etat_civil.retrieval.build_index import build_index
from rag_etat_civil.web.app import HTMX_CONFIG, create_app
from tests.fakes import FakeLLM, HashingEmbedder

REAL_DATA = Settings().data_dir
HTMX = {"HX-Request": "true"}


def reply(status="answered", answer="Selon l'article 36, ...", citations=(36,)):
    return json.dumps({"status": status, "answer": answer, "citations": list(citations)})


class BrokenLLM(FakeLLM):
    def generate_json(self, system_prompt, user_prompt, schema):
        raise LLMError("quota exceeded")


@pytest.fixture
def make_client(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Build a test client on a copy of the data, with a fake embedder and language model."""
    shutil.copytree(REAL_DATA / "processed", tmp_path / "processed")
    settings = Settings(
        data_dir=tmp_path,
        embedder="fake",
        llm_provider="fake",
        min_similarity=0.0,  # the fake embedder's similarities mean nothing
        max_question_length=50,
    )
    build_index(load_chunks(tmp_path), HashingEmbedder()).save(settings.index_dir)
    monkeypatch.setitem(EMBEDDERS, "fake", lambda s: HashingEmbedder())

    def make(llm: FakeLLM | None = None, *, index: bool = True):
        if not index:
            shutil.rmtree(settings.index_dir)
        monkeypatch.setitem(LLM_PROVIDERS, "fake", lambda s: llm or FakeLLM())
        app = create_app(settings)
        app.config["TESTING"] = True
        return app.test_client()

    return make


@pytest.fixture
def client():
    """A client for the pages that need no search engine."""
    app = create_app(Settings(max_question_length=50))
    app.config["TESTING"] = True
    return app.test_client()


# --- the page ----------------------------------------------------------------------------------


def test_index_shows_disclaimer(client):
    html = client.get("/").get_data(as_text=True)
    assert "ne remplace pas un avis juridique" in html


def test_security_headers(client):
    response = client.get("/")
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_footer_links_to_official_source(client):
    html = client.get("/").get_data(as_text=True)
    assert 'href="https://prc.cm/' in html
    assert 'rel="noopener noreferrer"' in html


def test_htmx_shows_the_unavailable_message_of_a_503():
    assert '{"code":"503","swap":true,"error":false}' in HTMX_CONFIG


# --- /health -----------------------------------------------------------------------------------


def test_health_is_ok_when_the_index_is_built(make_client):
    body = make_client().get("/health").get_json()

    assert body["status"] == "ok"
    assert body["index_ready"] is True
    assert body["articles"] > 100


def test_health_is_degraded_without_an_index_but_still_answers(make_client):
    response = make_client(index=False).get("/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "degraded"
    assert response.get_json()["index_ready"] is False


# --- /ask (the form) ---------------------------------------------------------------------------


def test_ask_shows_the_answer_and_links_the_cited_articles(make_client):
    client = make_client(FakeLLM(reply()))

    response = client.post("/ask", data={"question": "article 36"}, headers=HTMX)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Selon l&#39;article 36" in html
    assert 'href="/articles/36"' in html
    assert "<html" not in html


def test_ask_shows_a_refusal_as_an_answer(make_client):
    client = make_client(FakeLLM(reply(status="refused", answer="", citations=())))

    response = client.post("/ask", data={"question": "capitale ?"}, headers=HTMX)

    assert response.status_code == 200
    assert "Je ne trouve pas la réponse dans le texte de la loi." in response.get_data(as_text=True)


def test_ask_escapes_html(make_client):
    client = make_client(FakeLLM(reply(status="refused", citations=())))

    response = client.post("/ask", data={"question": "<script>alert(1)</script>"})
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_ask_empty_question(make_client):
    response = make_client().post("/ask", data={"question": "   "})
    assert response.status_code == 422


def test_ask_too_long(make_client):
    response = make_client().post("/ask", data={"question": "x" * 51})
    assert response.status_code == 422
    assert "trop longue" in response.get_data(as_text=True)


def test_ask_returns_the_full_page_without_htmx(make_client):
    client = make_client(FakeLLM(reply()))

    html = client.post("/ask", data={"question": "article 36"}).get_data(as_text=True)

    assert "<html" in html
    assert "Selon l&#39;article 36" in html


def test_ask_says_the_service_is_unavailable_when_the_language_model_fails(make_client):
    response = make_client(BrokenLLM()).post("/ask", data={"question": "article 36"}, headers=HTMX)

    assert response.status_code == 503
    assert "momentanément indisponible" in response.get_data(as_text=True)
    assert "quota" not in response.get_data(as_text=True)


def test_ask_says_the_service_is_not_ready_without_an_index(make_client):
    response = make_client(index=False).post("/ask", data={"question": "article 36"}, headers=HTMX)

    assert response.status_code == 503
    assert "pas prêt" in response.get_data(as_text=True)


# --- /api/ask ----------------------------------------------------------------------------------


def test_api_ask_returns_a_typed_answer(make_client):
    client = make_client(FakeLLM(reply()))

    response = client.post("/api/ask", json={"question": "article 36"})
    body = response.get_json()

    assert response.status_code == 200
    assert body["status"] == "answered"
    assert [c["article"] for c in body["citations"]] == [36]
    assert isinstance(body["citations"][0]["page"], int)


def test_api_ask_returns_a_refusal_with_its_reason(make_client):
    client = make_client(FakeLLM(reply(status="refused", citations=())))

    body = client.post("/api/ask", json={"question": "capitale ?"}).get_json()

    assert body["status"] == "refused"
    assert body["reason"] == "model_refused"


@pytest.mark.parametrize("payload", [None, {}, {"question": 12}, [1, 2]])
def test_api_ask_rejects_a_wrong_body(make_client, payload):
    response = make_client().post("/api/ask", json=payload)

    assert response.status_code == 422
    assert "question" in response.get_json()["error"]


def test_api_ask_rejects_an_empty_or_too_long_question(make_client):
    client = make_client()

    assert client.post("/api/ask", json={"question": " "}).status_code == 422
    assert client.post("/api/ask", json={"question": "x" * 51}).status_code == 422


def test_api_ask_reports_a_language_model_failure_as_503(make_client):
    response = make_client(BrokenLLM()).post("/api/ask", json={"question": "article 36"})

    assert response.status_code == 503
    assert "momentanément indisponible" in response.get_json()["error"]


# --- /articles/<number> ------------------------------------------------------------------------


def test_article_page_shows_the_exact_text_and_its_pages(make_client):
    response = make_client().get("/articles/36")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Article 36" in html
    assert "du PDF officiel" in html


def test_article_page_for_an_unknown_article_is_a_404(make_client):
    response = make_client().get("/articles/999")

    assert response.status_code == 404
    assert "n&#39;existe pas" in response.get_data(as_text=True)


def test_article_route_only_accepts_numbers(make_client):
    assert make_client().get("/articles/abc").status_code == 404


def test_api_article_returns_a_typed_article(make_client):
    body = make_client().get("/api/articles/36").get_json()

    assert body["number"] == 36
    assert body["text"]
    assert body["page_start"] <= body["page_end"]
    assert isinstance(body["breadcrumb"], list)


def test_api_article_for_an_unknown_article_is_a_404(make_client):
    response = make_client().get("/api/articles/999")

    assert response.status_code == 404
    assert "999" in response.get_json()["error"]
