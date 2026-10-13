"""WSGI entry point: `gunicorn rag_etat_civil.web.wsgi:app`."""

import logging

from rag_etat_civil.web.app import create_app
from rag_etat_civil.web.engine import EngineUnavailable

app = create_app()

try:
    app.extensions["engine"].preload()  # the first visitor should not wait for the model
except EngineUnavailable as error:
    # The application still starts: /health says what is missing and the next request retries.
    logging.getLogger(__name__).error("The search engine could not be loaded: %s", error)
