import re

from rag_etat_civil.answering.models import Answer, Citation, RefusalReason
from rag_etat_civil.evaluation.answers import (
    AnswerScore,
    Verdict,
    count_verdicts,
    fact_present,
    score_answer,
)
from rag_etat_civil.evaluation.dataset import EvalQuestion, load_questions


def question(**changes) -> EvalQuestion:
    base = {
        "id": "qx",
        "category": "cascade",
        "question": "Dans quel délai déclarer une naissance ?",
        "expected_status": "answered",
        "expected_articles": [10, 12],
        "also_accepted_articles": [11],
        "facts": [["90", "quatre-vingt-dix"], ["douze", "12"]],
        "forbidden_patterns": [],
        "reference_answer": "Une réponse.",
        "note": None,
    }
    return EvalQuestion.model_validate(base | changes)


def answered(text: str, *articles: int) -> Answer:
    return Answer(
        status="answered", text=text, citations=[Citation(article=a, page=1) for a in articles]
    )


def refused() -> Answer:
    return Answer(
        status="refused",
        text="Je ne trouve pas la réponse dans le texte de la loi.",
        reason=RefusalReason.MODEL_REFUSED,
    )


COMPLETE = "Dans les 90 jours (article 10), puis 12 mois sur réquisition (article 12)."


def test_a_complete_answer_is_ok():
    score = score_answer(question(), answered(COMPLETE, 10, 12))

    assert score == AnswerScore(Verdict.OK)


def test_a_missing_fact_makes_the_answer_partial():
    score = score_answer(question(), answered("Dans les 90 jours (article 10).", 10, 12))

    assert score.verdict is Verdict.PARTIAL
    assert score.missing_facts == (("douze", "12"),)
    assert score.missing_citations == ()


def test_an_expected_article_that_is_not_cited_makes_the_answer_partial():
    score = score_answer(question(), answered(COMPLETE, 10))

    assert score.verdict is Verdict.PARTIAL
    assert score.missing_citations == (12,)


def test_an_accepted_extra_article_is_not_a_problem():
    assert score_answer(question(), answered(COMPLETE, 10, 11, 12)).verdict is Verdict.OK


def test_an_unlisted_article_on_a_complete_answer_is_left_to_review():
    score = score_answer(question(), answered(COMPLETE, 10, 12, 99))

    assert score.verdict is Verdict.REVIEW
    assert score.unexpected_citations == (99,)


def test_an_incomplete_answer_stays_partial_even_with_an_unlisted_article():
    score = score_answer(question(), answered("Dans les 90 jours.", 10, 99))

    assert score.verdict is Verdict.PARTIAL
    assert score.unexpected_citations == (99,)


def test_a_refusal_on_an_answerable_question_fails():
    assert score_answer(question(), refused()).verdict is Verdict.FAILED


def test_a_tolerated_refusal_is_counted_apart():
    q = question(tolerated_status="refused")

    assert score_answer(q, refused()).verdict is Verdict.TOLERATED


def test_a_forbidden_pattern_fails_even_with_the_right_facts():
    q = question(forbidden_patterns=["amende"])

    score = score_answer(q, answered(COMPLETE + " Une amende de 5000.", 10, 12))

    assert score.verdict is Verdict.FAILED
    assert score.forbidden_hits == ("amende",)


def test_forbidden_patterns_ignore_case():
    q = question(forbidden_patterns=["Yaound"])

    assert score_answer(q, answered("YAOUNDÉ.", 10, 12)).verdict is Verdict.FAILED


def refusal_question(**changes) -> EvalQuestion:
    base = {"expected_status": "refused", "expected_articles": [], "facts": []}
    return question(**(base | changes))


def test_a_refusal_is_ok_when_a_refusal_is_expected():
    assert score_answer(refusal_question(), refused()).verdict is Verdict.OK


def test_an_answer_to_a_question_to_refuse_fails():
    assert score_answer(refusal_question(), answered("Voici.", 10)).verdict is Verdict.FAILED


def test_a_tolerated_answer_with_an_unlisted_article_is_left_to_review():
    q = refusal_question(tolerated_status="answered", also_accepted_articles=[1])

    fine = score_answer(q, answered("La loi ne le précise pas (article 1).", 1))
    wrong = score_answer(q, answered("Voici.", 55))

    assert fine.verdict is Verdict.TOLERATED
    assert wrong.verdict is Verdict.REVIEW


def test_a_tolerated_answer_still_fails_on_a_forbidden_pattern():
    q = refusal_question(
        tolerated_status="answered", also_accepted_articles=[1], forbidden_patterns=[r"\d+\s*ans"]
    )

    assert score_answer(q, answered("18 ans (article 1).", 1)).verdict is Verdict.FAILED


def test_facts_are_found_as_whole_words():
    assert fact_present(["90"], "dans les 90 jours")
    assert not fact_present(["90"], "dans les 190 jours")
    assert not fact_present(["12"], "article 120")


def test_facts_ignore_case_spaces_and_typographic_apostrophes():
    curly_apostrophe, no_break_space = chr(0x2019), chr(0xA0)
    text = f"le NUMÉRO D{curly_apostrophe}IDENTIFICATION{no_break_space}personnel"

    assert fact_present(["Numéro d'Identification"], text)


def test_one_spelling_of_a_group_is_enough():
    assert fact_present(["quatre-vingt-dix", "90"], "quatre-vingt-dix jours")


def test_verdicts_are_counted():
    scores = [AnswerScore(Verdict.OK), AnswerScore(Verdict.OK), AnswerScore(Verdict.FAILED)]

    counts = count_verdicts(scores)

    assert counts[Verdict.OK] == 2
    assert counts[Verdict.FAILED] == 1
    assert counts[Verdict.PARTIAL] == 0


def test_the_reference_answers_of_the_dataset_pass_their_own_checks():
    """A reference answer is the ideal answer: it must get the best verdict."""
    for q in load_questions():
        if q.expected_status != "answered":
            continue
        cited = [int(n) for n in re.findall(r"art\. (\d+)", q.reference_answer)]
        reference = Answer(
            status="answered",
            text=q.reference_answer,
            citations=[Citation(article=a, page=1) for a in dict.fromkeys(cited)],
        )
        assert score_answer(q, reference).verdict is Verdict.OK, q.id
