.PHONY: install run lint format test check

install:
	uv sync

run:
	uv run flask --app rag_etat_civil.web.wsgi:app run --debug

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

test:
	uv run pytest

check: lint test
