"""Checks on the evaluation questions: they must be well formed and agree with the law."""

import re
from pathlib import Path

import pytest
from rag_etat_civil.evaluation.dataset import load_questions

from rag_etat_civil.ingestion.build import load_articles

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = load_questions()  # also validates the file: fields, categories, consistency
ARTICLES = {article.number: article for article in load_articles(ROOT / "data")}


def test_there_are_between_15_and_25_questions():
    assert 15 <= len(QUESTIONS) <= 25


@pytest.mark.parametrize("q", QUESTIONS, ids=lambda q: q.id)
def test_cited_articles_exist_in_the_law(q):
    for number in q.accepted_articles:
        assert number in ARTICLES, f"article {number} does not exist"


@pytest.mark.parametrize("q", [q for q in QUESTIONS if q.facts], ids=lambda q: q.id)
def test_every_expected_fact_appears_in_the_cited_articles(q):
    """Each group of facts lists spellings of one fact; one of them must be in the law's text."""
    text = " ".join(ARTICLES[n].text for n in q.accepted_articles).casefold()
    for group in q.facts:
        assert any(variant.casefold() in text for variant in group), group


def test_articles_asked_by_number_match_the_expected_article():
    for q in QUESTIONS:
        match = re.search(r"article\s+(\d+)", q.question, re.IGNORECASE)
        if match:
            assert int(match.group(1)) in q.expected_articles
