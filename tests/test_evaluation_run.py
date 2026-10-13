import json

from rag_etat_civil.answering.models import Answer, Citation
from rag_etat_civil.evaluation.answers import Verdict
from rag_etat_civil.evaluation.answers_run import (
    AnswerCache,
    RunConfig,
    prompt_hash,
    run_questions,
)
from rag_etat_civil.evaluation.dataset import EvalQuestion
from rag_etat_civil.llm.base import LLMError


def question(id: str = "q1", **changes) -> EvalQuestion:
    base = {
        "id": id,
        "category": "direct",
        "question": f"Question {id} ?",
        "expected_status": "answered",
        "expected_articles": [10],
        "also_accepted_articles": [],
        "facts": [["90"]],
        "forbidden_patterns": [],
        "reference_answer": "Une réponse.",
        "note": None,
    }
    return EvalQuestion.model_validate(base | changes)


def config(**changes) -> RunConfig:
    base = {
        "model_id": "fake:model",
        "top_k": 8,
        "min_similarity": 0.0,
        "prompt_name": "current",
        "prompt_hash": prompt_hash("prompt"),
    }
    return RunConfig(**(base | changes))


GOOD = Answer(
    status="answered", text="90 jours (article 10).", citations=[Citation(article=10, page=3)]
)


class ScriptedAnswerer:
    """Answers with GOOD, or raises for the questions listed in `failing`."""

    def __init__(self, failing: set[str] = frozenset()) -> None:
        self.asked: list[str] = []
        self._failing = failing

    def answer(self, text: str) -> Answer:
        self.asked.append(text)
        if text in self._failing:
            raise LLMError("quota exceeded")
        return GOOD


def test_every_question_is_asked_and_scored():
    answerer = ScriptedAnswerer()

    runs = run_questions([question("q1"), question("q2")], answerer, config(), AnswerCache())

    assert answerer.asked == ["Question q1 ?", "Question q2 ?"]
    assert [run.score.verdict for run in runs] == [Verdict.OK, Verdict.OK]
    assert not any(run.cached for run in runs)


def test_a_second_run_uses_the_cache_instead_of_the_model():
    cache = AnswerCache()
    run_questions([question()], ScriptedAnswerer(), config(), cache)
    second = ScriptedAnswerer()

    runs = run_questions([question()], second, config(), cache)

    assert second.asked == []
    assert runs[0].cached
    assert runs[0].answer == GOOD


def test_refresh_ignores_the_cache():
    cache = AnswerCache()
    run_questions([question()], ScriptedAnswerer(), config(), cache)
    second = ScriptedAnswerer()

    run_questions([question()], second, config(), cache, refresh=True)

    assert second.asked == ["Question q1 ?"]


def test_another_setup_does_not_reuse_an_answer():
    cache = AnswerCache()
    run_questions([question()], ScriptedAnswerer(), config(), cache)

    for other in (config(top_k=15), config(min_similarity=0.8), config(prompt_hash="other")):
        answerer = ScriptedAnswerer()
        run_questions([question()], answerer, other, cache)
        assert answerer.asked, other
        assert other.cache_key("Question q1 ?") != config().cache_key("Question q1 ?")


def test_a_failure_is_recorded_not_cached_and_does_not_stop_the_run():
    cache = AnswerCache()
    answerer = ScriptedAnswerer(failing={"Question q1 ?"})

    runs = run_questions([question("q1"), question("q2")], answerer, config(), cache)

    assert runs[0].answer is None
    assert runs[0].error == "quota exceeded"
    assert runs[0].score.verdict is Verdict.ERROR
    assert runs[1].score.verdict is Verdict.OK
    assert cache.get(config().cache_key("Question q1 ?")) is None
    assert cache.get(config().cache_key("Question q2 ?")) is not None


def test_the_cache_survives_in_a_file(tmp_path):
    path = tmp_path / "eval" / "answers.json"
    run_questions([question()], ScriptedAnswerer(), config(), AnswerCache(path))

    second = ScriptedAnswerer()
    runs = run_questions([question()], second, config(), AnswerCache(path))

    assert second.asked == []
    assert runs[0].cached


def test_an_unreadable_cache_file_is_ignored(tmp_path):
    path = tmp_path / "answers.json"
    path.write_text("{not json", encoding="utf-8")
    answerer = ScriptedAnswerer()

    run_questions([question()], answerer, config(), AnswerCache(path))

    assert answerer.asked == ["Question q1 ?"]


def test_a_damaged_entry_is_treated_as_missing(tmp_path):
    path = tmp_path / "answers.json"
    key = config().cache_key("Question q1 ?")
    path.write_text(json.dumps({key: {"answer": {"status": "maybe"}, "seconds": 1}}), "utf-8")

    assert AnswerCache(path).get(key) is None


def test_the_pause_only_follows_real_calls():
    cache = AnswerCache()
    pauses: list[float] = []
    run_questions(
        [question("q1")], ScriptedAnswerer(), config(), cache, pause=2.5, sleep=pauses.append
    )
    assert pauses == [2.5]

    run_questions(
        [question("q1")], ScriptedAnswerer(), config(), cache, pause=2.5, sleep=pauses.append
    )
    assert pauses == [2.5]  # the second run found the answer in the cache


def test_results_are_reported_one_by_one():
    seen = []

    run_questions(
        [question("q1"), question("q2")],
        ScriptedAnswerer(),
        config(),
        AnswerCache(),
        on_result=lambda run: seen.append(run.question.id),
    )

    assert seen == ["q1", "q2"]
