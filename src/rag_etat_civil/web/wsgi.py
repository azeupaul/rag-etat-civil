"""Point d'entrée WSGI : `gunicorn rag_etat_civil.web.wsgi:app`."""

from rag_etat_civil.web.app import create_app

app = create_app()
