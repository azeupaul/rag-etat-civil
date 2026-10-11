import pytest

from rag_etat_civil.retrieval.lookup import find_article_numbers


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Que dit l'article 36 ?", [36]),
        ("Que dit l'Article 36 ?", [36]),
        ("art. 36", [36]),
        ("art 36", [36]),
        ("article 1er", [1]),
        ("l'article premier", [1]),
        ("articles 10 et 11", [10, 11]),
        ("les articles 10, 11 et 12", [10, 11, 12]),
        ("article 10 ou article 20", [10, 20]),
        ("quel est l'alinéa 2 de l'article 9 ?", [9]),
        ("article 36 article 36", [36]),
    ],
)
def test_article_numbers_are_found(question, expected):
    assert find_article_numbers(question, max_article=130) == expected


@pytest.mark.parametrize(
    "question",
    [
        "Dans quel délai déclarer une naissance ?",
        "la loi 2024/016 du 23 décembre 2024",
        "il y a 36 articles",
        "article",
        "",
    ],
)
def test_nothing_is_found_without_an_article_reference(question):
    assert find_article_numbers(question, max_article=130) == []


def test_numbers_outside_the_law_are_ignored():
    assert find_article_numbers("article 0", max_article=130) == []
    assert find_article_numbers("article 131", max_article=130) == []
    assert find_article_numbers("articles 5 et 500", max_article=130) == [5]


def test_a_year_is_not_an_article_number():
    assert find_article_numbers("article 2024", max_article=130) == []
