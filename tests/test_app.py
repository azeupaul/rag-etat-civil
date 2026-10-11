import pytest

from rag_etat_civil.config import Settings
from rag_etat_civil.web.app import create_app


@pytest.fixture
def client():
    app = create_app(Settings(max_question_length=50))
    app.config["TESTING"] = True
    return app.test_client()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_index_shows_disclaimer(client):
    html = client.get("/").get_data(as_text=True)
    assert "ne remplace pas un avis juridique" in html


def test_security_headers(client):
    response = client.get("/")
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_ask_escapes_html(client):
    response = client.post("/ask", data={"question": "<script>alert(1)</script>"})
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_ask_empty_question(client):
    response = client.post("/ask", data={"question": "   "})
    assert response.status_code == 422


def test_ask_too_long(client):
    response = client.post("/ask", data={"question": "x" * 51})
    assert response.status_code == 422
    assert "trop longue" in response.get_data(as_text=True)


def test_ask_returns_full_page_without_htmx(client):
    html = client.post("/ask", data={"question": "Bonjour"}).get_data(as_text=True)
    assert "<html" in html


def test_ask_returns_partial_with_htmx(client):
    response = client.post("/ask", data={"question": "Bonjour"}, headers={"HX-Request": "true"})
    assert "<html" not in response.get_data(as_text=True)


def test_footer_links_to_official_source(client):
    html = client.get("/").get_data(as_text=True)
    assert 'href="https://prc.cm/' in html
    assert 'rel="noopener noreferrer"' in html
