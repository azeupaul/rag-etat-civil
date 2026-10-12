"""Tests for the `make ask` command and the answerer factory."""

import json
import shutil
from pathlib import Path

import pytest

from rag_etat_civil.answering import ask
from rag_etat_civil.answering.models import Answer, Citation, RefusalReason
from rag_etat_civil.config import Settings
from rag_etat_civil.embeddings.registry import EMBEDDERS
from rag_etat_civil.ingestion.build import load_chunks
from rag_etat_civil.llm.base import LLMError
from rag_etat_civil.llm.registry import LLM_PROVIDERS
from rag_etat_civil.retrieval.build_index import build_index
from tests.fakes import FakeLLM, HashingEmbedder

REAL_DATA = Settings().data_dir


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """A data directory with an index built by the fake embedder, and fake providers."""
    shutil.copytree(REAL_DATA / "processed", tmp_path / "processed")
    settings = Settings(data_dir=tmp_path)
    build_index(load_chunks(tmp_path), HashingEmbedder()).save(settings.index_dir)

    monkeypatch.setitem(EMBEDDERS, "fake", lambda s: HashingEmbedder())
    monkeypatch.setenv("EMBEDDER", "fake")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    return monkeypatch


def use_llm(monkeypatch: pytest.MonkeyPatch, llm: FakeLLM) -> None:
    monkeypatch.setitem(LLM_PROVIDERS, "fake", lambda s: llm)


def test_format_answer_lists_the_citations_and_their_pages():
    answer = Answer(
        status="answered", text="Selon l'article 10 ...", citations=[Citation(article=10, page=7)]
    )
    text = ask.format_answer(answer)
    assert "Selon l'article 10" in text
    assert "article 10 (PDF p. 7)" in text


def test_format_answer_shows_the_reason_of_a_refusal():
    answer = Answer(status="refused", text="Je ne trouve pas.", reason=RefusalReason.OUT_OF_SCOPE)
    assert "[refus : out_of_scope]" in ask.format_answer(answer)


def test_ask_prints_a_checked_answer(configured, capsys):
    reply = json.dumps({"status": "answered", "answer": "Selon l'article 36.", "citations": [36]})
    use_llm(configured, FakeLLM(reply))

    assert ask.main(["article", "36"]) == 0

    out = capsys.readouterr().out
    assert "Selon l'article 36." in out
    assert "article 36 (PDF p." in out


def test_ask_reports_a_missing_index(configured, tmp_path, capsys):
    shutil.rmtree(tmp_path / "index")
    use_llm(configured, FakeLLM())

    assert ask.main(["naissance"]) == 1
    assert "make index" in capsys.readouterr().out


def test_ask_reports_a_wrong_language_model_setup(configured, capsys):
    configured.setenv("LLM_PROVIDER", "unknown")

    assert ask.main(["naissance"]) == 1
    assert "Unknown LLM_PROVIDER" in capsys.readouterr().out


def test_ask_reports_a_provider_failure(configured, capsys):
    class BrokenLLM(FakeLLM):
        def generate_json(self, system_prompt, user_prompt, schema):
            raise LLMError("quota exceeded")

    use_llm(configured, BrokenLLM())

    assert ask.main(["naissance"]) == 2
    assert "quota exceeded" in capsys.readouterr().out
