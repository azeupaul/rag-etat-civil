"""Flask application: home page, /ask route (HTMX) and /health."""

from __future__ import annotations

from flask import Flask, Response, jsonify, render_template, request
from flask_htmx import HTMX

from rag_etat_civil import __version__
from rag_etat_civil.config import OFFICIAL_SOURCE_URL, Settings

# By default htmx does not swap the content of 4xx responses: we explicitly allow 422
# (invalid question) so the error message is displayed in the page.
# Inline styles and eval are disabled so that the app works under a strict CSP.
HTMX_CONFIG = (
    '{"includeIndicatorStyles":false,"allowEval":false,"responseHandling":['
    '{"code":"204","swap":false},'
    '{"code":"[23]..","swap":true},'
    '{"code":"422","swap":true,"error":false},'
    '{"code":"[45]..","swap":false,"error":true}]}'
)

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)


def create_app(settings: Settings | None = None) -> Flask:
    """Build the application (factory, so that tests can configure it)."""
    settings = settings or Settings.from_env()

    app = Flask(__name__)
    app.config["SETTINGS"] = settings
    app.jinja_env.globals.update(
        app_version=__version__,
        htmx_config=HTMX_CONFIG,
        max_question_length=settings.max_question_length,
        official_source_url=OFFICIAL_SOURCE_URL,
    )
    htmx = HTMX(app)

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.post("/ask")
    def ask() -> tuple[str, int] | str:
        question = request.form.get("question", "").strip()

        error = None
        if not question:
            error = "Saisissez une question."
        elif len(question) > settings.max_question_length:
            limit = settings.max_question_length
            error = f"La question est trop longue ({limit} caractères maximum)."

        if error:
            template, status = ("partials/error.html", 422)
            context = {"error": error}
        else:
            # E1: the RAG engine is not wired yet (retrieval in E3, generation in E4).
            template, status = ("partials/answer.html", 200)
            context = {"question": question}

        # Without JavaScript the form is submitted normally: return the whole page.
        if htmx:
            return render_template(template, **context), status
        return render_template("index.html", partial=template, **context), status

    @app.get("/health")
    def health() -> Response:
        return jsonify(status="ok", version=__version__)

    @app.after_request
    def add_security_headers(response: Response) -> Response:
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    return app
