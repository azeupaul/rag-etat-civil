"""Checks on the evaluation questions: they must be well formed and agree with the law."""

import json
import re
from pathlib import Path

import pytest

from rag_etat_civil.ingestion.build import load_articles

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = json.loads((ROOT / "eval" / "questions.json").read_text(encoding="utf-8"))
ARTICLES = {article.number: article for article in load_articles(ROOT / "data")}
CATEGORIES = {
    "direct",
    "cascade",
    "colloquial",
    "lookup",
    "limit",
    "variant",
    "out_of_law",
    "off_topic",
    "adversarial",
}
FIELDS = {
    "id",
    "category",
    "question",
    "expected_status",
    "expected_articles",
    "also_accepted_articles",
    "facts",
    "forbidden_patterns",
    "reference_answer",
    "note",
}


def ids():
    return [q["id"] for q in QUESTIONS]


def test_there_are_between_15_and_25_questions():
    assert 15 <= len(QUESTIONS) <= 25


def test_ids_are_unique():
    assert len(set(ids())) == len(ids())


@pytest.mark.parametrize("q", QUESTIONS, ids=ids())
def test_each_question_is_well_formed(q):
    assert FIELDS <= set(q) <= FIELDS | {"tolerated_status"}
    assert q["category"] in CATEGORIES
    assert q["question"].strip()
    assert q["reference_answer"].strip()
    assert q["expected_status"] in {"answered", "refused"}
    assert q.get("tolerated_status") in {None, "answered", "refused"}
    for pattern in q["forbidden_patterns"]:
        re.compile(pattern)


@pytest.mark.parametrize("q", QUESTIONS, ids=ids())
def test_cited_articles_exist_in_the_law(q):
    for number in q["expected_articles"] + q["also_accepted_articles"]:
        assert number in ARTICLES, f"article {number} does not exist"


@pytest.mark.parametrize("q", QUESTIONS, ids=ids())
def test_an_answerable_question_names_its_articles_and_a_refused_one_does_not(q):
    if q["expected_status"] == "answered":
        assert q["expected_articles"]
    else:
        assert not q["expected_articles"]


@pytest.mark.parametrize("q", [q for q in QUESTIONS if q["facts"]], ids=lambda q: q["id"])
def test_every_expected_fact_appears_in_the_cited_articles(q):
    """Each group of facts lists spellings of one fact; one of them must be in the law's text."""
    numbers = q["expected_articles"] + q["also_accepted_articles"]
    text = " ".join(ARTICLES[n].text for n in numbers).casefold()
    for group in q["facts"]:
        assert any(variant.casefold() in text for variant in group), group


def test_articles_asked_by_number_match_the_expected_article():
    for q in QUESTIONS:
        match = re.search(r"article\s+(\d+)", q["question"], re.IGNORECASE)
        if match:
            assert int(match.group(1)) in q["expected_articles"]
