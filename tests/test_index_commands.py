"""Tests for the index build, the retriever factory and the search command."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from rag_etat_civil.config import Settings
from rag_etat_civil.embeddings.registry import EMBEDDERS
from rag_etat_civil.ingestion.build import load_articles, load_chunks
from rag_etat_civil.retrieval import build_index as build_index_module
from rag_etat_civil.retrieval import search
from rag_etat_civil.retrieval.build_index import build_index
from rag_etat_civil.retrieval.factory import IndexNotBuiltError, load_retriever
from tests.fakes import HashingEmbedder

REAL_DATA = Settings().data_dir


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    shutil.copytree(REAL_DATA / "processed", tmp_path / "processed")
    return tmp_path


@pytest.fixture
def built(data_dir: Path) -> Settings:
    settings = Settings(data_dir=data_dir)
    chunks = load_chunks(data_dir)
    build_index(chunks, HashingEmbedder()).save(settings.index_dir)
    return settings


def test_index_dir_is_inside_data_dir():
    assert Settings().index_dir == Settings().data_dir / "index"


def test_build_index_has_one_vector_per_chunk(data_dir: Path):
    chunks = load_chunks(data_dir)
    index = build_index(chunks, HashingEmbedder())
    assert len(index) == len(chunks)


def test_load_retriever_without_index_explains_how_to_build_it(data_dir: Path):
    with pytest.raises(IndexNotBuiltError, match="make index"):
        load_retriever(Settings(data_dir=data_dir), HashingEmbedder())


def test_load_retriever_roundtrip(built: Settings):
    retriever = load_retriever(built, HashingEmbedder())
    hits = retriever.retrieve("article 36")
    assert hits[0].chunk.article == 36


def test_format_hit_shows_article_sources_and_page(built: Settings):
    retriever = load_retriever(built, HashingEmbedder())
    hit = retriever.retrieve("article 10")[0]
    article = {a.number: a for a in load_articles(built.data_dir)}[hit.chunk.article]
    text = search.format_hit(1, hit, article)
    assert text.startswith("1. Article 10")
    assert f"PDF p. {article.page_start}" in text


@pytest.fixture
def fake_env(monkeypatch: pytest.MonkeyPatch, data_dir: Path) -> Path:
    monkeypatch.setitem(EMBEDDERS, "fake", lambda settings: HashingEmbedder())
    monkeypatch.setenv("EMBEDDER", "fake")
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    return data_dir


def test_cli_end_to_end(fake_env: Path, capsys: pytest.CaptureFixture[str]):
    build_index_module.main()
    assert search.main(["article", "36"]) == 0
    assert "Article 36" in capsys.readouterr().out


def test_cli_search_without_index_returns_error(fake_env: Path, capsys: pytest.CaptureFixture[str]):
    assert search.main(["naissance"]) == 1
    assert "make index" in capsys.readouterr().out
