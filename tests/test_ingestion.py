from pathlib import Path

import pytest

from rag_etat_civil.ingestion.build import (
    ARTICLES_PATH,
    CHUNKS_PATH,
    RAW_PATH,
    render_articles,
    render_chunks,
)
from rag_etat_civil.ingestion.chunking import MAX_ARTICLE_CHARS, chunk_articles
from rag_etat_civil.ingestion.parser import ParseError, parse_file, parse_law

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(scope="module")
def articles():
    return parse_file(DATA_DIR / RAW_PATH)


@pytest.fixture(scope="module")
def chunks(articles):
    return chunk_articles(articles)


def test_130_articles_in_order(articles):
    assert [a.number for a in articles] == list(range(1, 131))


def test_no_formatting_leftovers(articles):
    for article in articles:
        assert "[[p." not in article.text
        assert not article.text.startswith("ARTICLE")
        assert "Yaoundé, le" not in article.text


def test_article_1(articles):
    article = articles[0]
    assert article.text.startswith("(1) La présente loi porte organisation")
    assert article.page_start == 2
    assert article.chapter.numeral == "I"
    assert article.section.numeral == "I"
    assert article.paragraph is None


def test_chapter_without_section(articles):
    """Article 9 is in chapter II, before the first section."""
    article = articles[8]
    assert article.chapter.numeral == "II"
    assert article.section is None


def test_lower_levels_are_reset(articles):
    assert articles[9].section.numeral == "I"  # article 10
    assert articles[9].paragraph is None
    assert articles[36].paragraph.numeral == "I"  # article 37
    assert articles[39].paragraph.numeral == "II"  # article 40
    assert articles[27].paragraph is None  # article 28, chapter III section I


def test_official_typo_in_paragraph_heading_is_recognized(articles):
    """The official text says "PARAGRAGRHE I": the structure must still be right."""
    assert articles[87].paragraph.numeral == "I"  # article 88
    assert articles[90].paragraph.numeral == "II"  # article 91


def test_multi_line_title(articles):
    section = articles[55].section  # article 56, chapter IV section I
    assert section.title.endswith("PAR VOIE ADMINISTRATIVE")


def test_last_article_has_no_signature(articles):
    assert articles[-1].text.endswith("en français et en anglais./-")
    assert articles[-1].chapter.numeral == "X"


def test_paragraph_numbers_are_kept(articles):
    text = articles[121].text  # article 122
    assert text.count("\n(") >= 2
    assert "l'article 341 du Code Pénal" in text


def test_pages_are_consistent(articles):
    for article in articles:
        assert 1 <= article.page_start <= article.page_end <= 40
    assert [a.page_start for a in articles] == sorted(a.page_start for a in articles)


def test_non_consecutive_numbering_is_rejected():
    with pytest.raises(ParseError):
        parse_law("ARTICLE 1er.- Un.\n\nARTICLE 3.- Trois.\n")


def test_one_chunk_per_article_except_article_3(chunks):
    multi_part = {c.article for c in chunks if c.total > 1}
    assert multi_part == {3}
    assert len({c.article for c in chunks}) == 130


def test_long_articles_are_cut_without_loss(articles, chunks):
    too_long = {a.number for a in articles if len(a.text) > MAX_ARTICLE_CHARS}
    assert too_long == {3}
    parts = [c for c in chunks if c.article == 3]
    assert len(parts) > 3
    assert "\n".join(c.text for c in parts) == articles[2].text  # nothing lost, nothing added


def test_unique_ids_and_indexed_context(chunks):
    assert len({c.id for c in chunks}) == len(chunks)
    chunk = next(c for c in chunks if c.id == "art-010")
    assert chunk.indexed_text.endswith(chunk.text)
    assert "Article 10" in chunk.indexed_text
    assert "naissance" in chunk.indexed_text.lower()


def test_generated_files_are_up_to_date(articles, chunks):
    """data/processed must match the source text (run `make ingest`)."""
    assert (DATA_DIR / ARTICLES_PATH).read_text(encoding="utf-8") == render_articles(articles)
    assert (DATA_DIR / CHUNKS_PATH).read_text(encoding="utf-8") == render_chunks(chunks)
