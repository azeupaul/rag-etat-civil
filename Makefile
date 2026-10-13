.PHONY: install run lint format test test-model test-llm check

install:
	uv sync --all-extras

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

test-model:
	uv run pytest -m model

test-llm:
	uv run pytest -m llm

check: lint test

.PHONY: ingest index search ask eval-retrieval eval-answers
ingest:
	uv run python -m rag_etat_civil.ingestion.build

index:
	uv run python -m rag_etat_civil.retrieval.build_index

search:
	@test -n "$(q)" || { echo 'usage: make search q="your question"'; exit 1; }
	@uv run python -m rag_etat_civil.retrieval.search "$(q)"

ask:
	@test -n "$(q)" || { echo 'usage: make ask q="your question"'; exit 1; }
	@uv run python -m rag_etat_civil.answering.ask "$(q)"

eval-retrieval:
	uv run python eval/run_eval.py retrieval

eval-answers:
	uv run python eval/run_eval.py answers $(args)
