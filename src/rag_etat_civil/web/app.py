"""Application Flask : page d'accueil, route /ask (HTMX) et /health."""

from __future__ import annotations

from flask import Flask, Response, jsonify, render_template, request
from flask_htmx import HTMX

from rag_etat_civil import __version__
from rag_etat_civil.config import Settings

# htmx ne remplace pas le contenu des réponses 4xx par défaut : on autorise explicitement
# le 422 (question invalide) pour afficher le message d'erreur dans la page.
# Les styles et eval inline sont désactivés pour tenir sous une CSP stricte.
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
    """Construit l'application (fabrique, pour pouvoir la configurer dans les tests)."""
    settings = settings or Settings.from_env()

    app = Flask(__name__)
    app.config["SETTINGS"] = settings
    app.jinja_env.globals.update(
        app_version=__version__,
        htmx_config=HTMX_CONFIG,
        max_question_length=settings.max_question_length,
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
            # E1 : moteur RAG non branché (récupération en E3, génération en E4).
            template, status = ("partials/answer.html", 200)
            context = {"question": question}

        # Sans JavaScript, le formulaire est envoyé normalement : on renvoie alors la page entière.
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
