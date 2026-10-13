from rag_etat_civil.answering.models import Answer, Citation, RefusalReason
from rag_etat_civil.evaluation.answers_report import render_answers_report
from rag_etat_civil.evaluation.answers_run import QuestionRun, RunConfig
from rag_etat_civil.evaluation.dataset import EvalQuestion


def question(id: str, **changes) -> EvalQuestion:
    base = {
        "id": id,
        "category": "cascade",
        "question": f"Question {id} ?",
        "expected_status": "answered",
        "expected_articles": [10, 12],
        "also_accepted_articles": [],
        "facts": [["90"], ["douze", "12"]],
        "forbidden_patterns": [],
        "reference_answer": "La référence.",
        "note": None,
    }
    return EvalQuestion.model_validate(base | changes)


def config(top_k: int) -> RunConfig:
    return RunConfig("fake:model", top_k, 0.0, "current", "abc")


def run(q: EvalQuestion, text: str, *articles: int, seconds: float = 2.0, cached=False):
    answer = Answer(
        status="answered", text=text, citations=[Citation(article=a, page=1) for a in articles]
    )
    return QuestionRun(q, answer, None, seconds, cached)


Q1, Q2 = question("q1"), question("q2", category="direct", expected_articles=[10], facts=[["90"]])


def report():
    complete = run(Q1, "90 jours (art. 10), 12 mois (art. 12).", 10, 12)
    partial = run(Q1, "90 jours (art. 10).", 10, seconds=3.0, cached=True)
    refusal = QuestionRun(
        Q2,
        Answer(status="refused", text="Je ne trouve pas.", reason=RefusalReason.MODEL_REFUSED),
        None,
        1.0,
        False,
    )
    error = QuestionRun(Q2, None, "quota exceeded", 0.5, False)
    return render_answers_report([(config(8), [partial, refusal]), (config(15), [complete, error])])


def test_the_report_compares_the_configurations_with_their_verdict_counts():
    text = report()

    assert "## Comparaison des configurations" in text
    assert "| k=8, seuil=0, prompt=current | 0 | 1 | 0 | 1 | 0 |" in text
    assert "| k=15, seuil=0, prompt=current | 1 | 0 | 0 | 0 | 1 |" in text


def test_the_report_gives_a_verdict_per_question_and_configuration():
    text = report()

    assert (
        "| id | catégorie | k=8, seuil=0, prompt=current | k=15, seuil=0, prompt=current |" in text
    )
    assert "| q1 | cascade | partiel | OK |" in text
    assert "| q2 | direct | ÉCHEC | erreur |" in text


def test_the_report_shows_the_reference_and_every_answer_for_reading():
    text = report()

    assert "> **Référence :** La référence." in text
    assert "90 jours (art. 10), 12 mois (art. 12)." in text
    assert "en cache" in text
    assert text.count("<details>") == 4


def test_the_report_explains_what_is_wrong_with_an_answer():
    text = report()

    assert "- Faits manquants : douze / 12" in text
    assert "- Articles attendus non cités : 12" in text
    assert "- Refus : `model_refused`" in text
    assert "- Erreur du modèle de langage : quota exceeded" in text


def test_the_median_time_ignores_answers_that_did_not_reach_the_model():
    gated = QuestionRun(
        Q2,
        Answer(status="refused", text="x", reason=RefusalReason.OUT_OF_SCOPE),
        None,
        0.0,
        False,
    )
    slow = run(Q1, "90 jours (art. 10), 12 mois (art. 12).", 10, 12, seconds=4.0)

    text = render_answers_report([(config(8), [gated, slow])])

    assert "| 4.0 s |" in text


def test_no_median_when_nothing_reached_the_model():
    error = QuestionRun(Q2, None, "quota exceeded", 0.5, False)

    assert "| - |" in render_answers_report([(config(8), [error])])
