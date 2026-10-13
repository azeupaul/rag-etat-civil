import json

import pytest
from pydantic import ValidationError

from rag_etat_civil.evaluation.dataset import EvalQuestion, load_questions


def raw(**changes):
    base = {
        "id": "qx",
        "category": "direct",
        "question": "Une question ?",
        "expected_status": "answered",
        "expected_articles": [10],
        "also_accepted_articles": [11],
        "facts": [["90", "quatre-vingt-dix"]],
        "forbidden_patterns": [],
        "reference_answer": "Une réponse.",
        "note": None,
    }
    return base | changes


def test_a_valid_question_is_loaded():
    q = EvalQuestion.model_validate(raw())

    assert q.tolerated_status is None
    assert q.accepted_articles == {10, 11}


def test_an_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        EvalQuestion.model_validate(raw(surprise=1))


def test_an_unknown_category_is_rejected():
    with pytest.raises(ValidationError):
        EvalQuestion.model_validate(raw(category="other"))


def test_an_invalid_regular_expression_is_rejected():
    with pytest.raises(ValidationError):
        EvalQuestion.model_validate(raw(forbidden_patterns=["("]))


def test_an_answerable_question_needs_expected_articles():
    with pytest.raises(ValidationError, match="expected articles"):
        EvalQuestion.model_validate(raw(expected_articles=[]))


def test_a_question_to_refuse_has_no_expected_articles():
    with pytest.raises(ValidationError, match="no expected articles"):
        EvalQuestion.model_validate(raw(expected_status="refused"))


def test_a_refused_question_without_articles_is_valid():
    q = EvalQuestion.model_validate(
        raw(expected_status="refused", expected_articles=[], also_accepted_articles=[])
    )

    assert q.accepted_articles == set()


def test_duplicate_ids_are_rejected(tmp_path):
    path = tmp_path / "questions.json"
    path.write_text(json.dumps([raw(), raw()]), encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate"):
        load_questions(path)
