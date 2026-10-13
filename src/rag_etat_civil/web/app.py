"""Flask application: the page, the questions (HTML and JSON), the articles and /health.

Routes
    GET  /                       the page with the question form
    POST /ask                    a question from the form (HTMX): returns the answer as HTML
    POST /api/ask                the same question as JSON: returns an `Answer`
    GET  /articles/<number>      the exact text of an article (HTML)
    GET  /api/articles/<number>  the same as JSON: an `ArticleView`
    GET  /health                 a `HealthStatus`
"""

from __future__ import annotations

from flask import Flask, Response, render_template, request
from flask_htmx import HTMX
from pydantic import BaseModel, ValidationError

from rag_etat_civil import __version__
from rag_etat_civil.answering.models import Answer
from rag_etat_civil.config import OFFICIAL_SOURCE_URL, Settings
from rag_etat_civil.llm.base import LLMError
from rag_etat_civil.web.engine import Engine, EngineUnavailable
from rag_etat_civil.web.schemas import ArticleView, AskRequest, ErrorResponse, HealthStatus

# By default htmx does not swap the content of 4xx and 5xx responses: we explicitly allow 422
# (invalid question) and 503 (service unavailable) so the message is displayed in the page.
# Inline styles and eval are disabled so that the app works under a strict CSP.
HTMX_CONFIG = (
    '{"includeIndicatorStyles":false,"allowEval":false,"responseHandling":['
    '{"code":"204","swap":false},'
    '{"code":"[23]..","swap":true},'
    '{"code":"422","swap":true,"error":false},'
    '{"code":"503","swap":true,"error":false},'
    '{"code":"[45]..","swap":false,"error":true}]}'
)

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)

# What visitors read. The technical cause goes to the logs, never to the page.
UNAVAILABLE_MESSAGE = "Le service est momentanément indisponible. Réessayez dans une minute."
NOT_READY_MESSAGE = "Le service n'est pas prêt : l'index de recherche est absent."
BAD_BODY_MESSAGE = 'Corps JSON attendu : {"question": "..."}.'


# Why the assistant did not answer, in words a visitor can act on (one entry per RefusalReason).
REFUSAL_HELP = {
    "out_of_scope": "Votre question ne semble pas porter sur la loi n° 2024/016.",
    "no_passage": "Aucun passage de la loi ne correspond à votre question. Reformulez-la.",
    "model_refused": (
        "Les passages retrouvés ne contiennent pas la réponse. La loi ne traite peut-être pas "
        "ce point, ou renvoie à un règlement. Vous pouvez reformuler la question."
    ),
    "invalid_answer": (
        "Une réponse a été produite mais ses citations n'ont pas pu être vérifiées, "
        "elle n'est donc pas affichée. Réessayez ou reformulez la question."
    ),
}

# Questions offered on the page. All of them are in eval/questions.json and were answered
# correctly by the evaluation: a visitor's first click should show the assistant at its best.
EXAMPLE_QUESTIONS = (
    "Qui doit déclarer la naissance d'un enfant né dans un hôpital, et dans quel délai ?",
    "Les services d'état civil sont-ils gratuits ? Et les copies d'actes ?",
    "Qu'est-ce que le NIPU ?",
    "Un acte d'état civil électronique a-t-il la même valeur qu'un acte sur papier ?",
)


def json_response(model: BaseModel, status: int = 200) -> Response:
    return Response(model.model_dump_json(), status=status, mimetype="application/json")


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> Flask:
    """Build the application (factory, so that tests can configure it)."""
    settings = settings or Settings.from_env()
    engine = engine or Engine(settings)

    app = Flask(__name__)
    app.config["SETTINGS"] = settings
    app.extensions["engine"] = engine
    app.jinja_env.globals.update(
        app_version=__version__,
        htmx_config=HTMX_CONFIG,
        max_question_length=settings.max_question_length,
        official_source_url=OFFICIAL_SOURCE_URL,
        example_questions=EXAMPLE_QUESTIONS,
        refusal_help=REFUSAL_HELP,
    )
    htmx = HTMX(app)

    def check_question(question: str) -> str | None:
        """The problem with the question, or None when it can be asked."""
        if not question:
            return "Saisissez une question."
        if len(question) > settings.max_question_length:
            return (
                f"La question est trop longue ({settings.max_question_length} caractères maximum)."
            )
        return None

    def run_question(question: str) -> tuple[Answer | None, str | None, int]:
        """Ask the question. Returns the answer or, failing that, a message and an HTTP status."""
        problem = check_question(question)
        if problem:
            return None, problem, 422
        try:
            return engine.answerer().answer(question), None, 200
        except EngineUnavailable as error:
            app.logger.error("The search engine is not available: %s", error)
            return None, NOT_READY_MESSAGE, 503
        except LLMError as error:
            app.logger.warning("The language model failed: %s", error)
            return None, UNAVAILABLE_MESSAGE, 503

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.post("/ask")
    def ask() -> tuple[str, int]:
        question = request.form.get("question", "").strip()
        answer, error, status = run_question(question)

        if answer is not None:
            template, context = "partials/answer.html", {"question": question, "answer": answer}
        else:
            template, context = "partials/error.html", {"error": error}

        # Without JavaScript the form is submitted normally: return the whole page.
        if htmx:
            return render_template(template, **context), status
        return render_template("index.html", partial=template, **context), status

    @app.post("/api/ask")
    def api_ask() -> Response:
        try:
            body = AskRequest.model_validate(request.get_json(silent=True))
        except ValidationError:
            return json_response(ErrorResponse(error=BAD_BODY_MESSAGE), 422)
        answer, error, status = run_question(body.question.strip())
        if answer is None:
            return json_response(ErrorResponse(error=error or UNAVAILABLE_MESSAGE), status)
        return json_response(answer)

    @app.get("/articles/<int:number>")
    def article_page(number: int) -> tuple[str, int]:
        try:
            article = engine.articles().get(number)
        except EngineUnavailable as error:
            app.logger.error("The articles are not available: %s", error)
            return render_template("article.html", number=number, error=NOT_READY_MESSAGE), 503
        if article is None:
            message = f"L'article {number} n'existe pas dans la loi."
            return render_template("article.html", number=number, error=message), 404
        return render_template("article.html", number=number, article=article), 200

    @app.get("/api/articles/<int:number>")
    def api_article(number: int) -> Response:
        try:
            article = engine.articles().get(number)
        except EngineUnavailable as error:
            app.logger.error("The articles are not available: %s", error)
            return json_response(ErrorResponse(error=NOT_READY_MESSAGE), 503)
        if article is None:
            message = f"L'article {number} n'existe pas dans la loi."
            return json_response(ErrorResponse(error=message), 404)
        return json_response(ArticleView.from_article(article))

    @app.get("/health")
    def health() -> Response:
        try:
            articles = len(engine.articles())
        except EngineUnavailable:
            articles = 0
        ready = engine.index_ready() and articles > 0
        status = HealthStatus(
            status="ok" if ready else "degraded",
            version=__version__,
            index_ready=engine.index_ready(),
            articles=articles,
        )
        return json_response(status)

    @app.after_request
    def add_security_headers(response: Response) -> Response:
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    return app
