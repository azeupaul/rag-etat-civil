"""Run the reference questions through the assistant, keeping the answers in a cache.

Asking a language model costs time and quota, so an answer is stored with the exact setup that
produced it (model, top_k, threshold, prompt). Running the evaluation again only calls the
model for what is new or changed.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from rag_etat_civil.answering.models import Answer
from rag_etat_civil.evaluation.answers import AnswerScore, Verdict, score_answer
from rag_etat_civil.evaluation.dataset import EvalQuestion
from rag_etat_civil.llm.base import LLMError


class Answering(Protocol):
    def answer(self, question: str) -> Answer: ...


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:10]


@dataclass(frozen=True, slots=True)
class RunConfig:
    """Everything that can change an answer, apart from the question itself."""

    model_id: str
    top_k: int
    min_similarity: float
    prompt_name: str
    prompt_hash: str

    @property
    def label(self) -> str:
        return f"k={self.top_k}, seuil={self.min_similarity:g}, prompt={self.prompt_name}"

    def cache_key(self, question: str) -> str:
        parts = [self.model_id, self.top_k, self.min_similarity, self.prompt_hash, question]
        return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode("utf-8")).hexdigest()


class AnswerCache:
    """A JSON file of answers. With no path, it only lives in memory."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._entries: dict[str, dict] = {}
        if path is not None and path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                loaded = {}  # an unreadable cache is only a cache: start again
            if isinstance(loaded, dict):
                self._entries = loaded

    def get(self, key: str) -> tuple[Answer, float] | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        try:
            return Answer.model_validate(entry["answer"]), float(entry["seconds"])
        except (KeyError, TypeError, ValueError, ValidationError):
            return None

    def put(self, key: str, answer: Answer, seconds: float) -> None:
        self._entries[key] = {"answer": answer.model_dump(mode="json"), "seconds": seconds}

    def save(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._entries, ensure_ascii=False, indent=1), "utf-8")
        temporary.replace(self._path)


@dataclass(frozen=True, slots=True)
class QuestionRun:
    question: EvalQuestion
    answer: Answer | None  # None when the language model could not be reached
    error: str | None
    seconds: float
    cached: bool

    @property
    def score(self) -> AnswerScore:
        if self.answer is None:
            return AnswerScore(Verdict.ERROR)
        return score_answer(self.question, self.answer)


def run_questions(
    questions: Sequence[EvalQuestion],
    answerer: Answering,
    config: RunConfig,
    cache: AnswerCache,
    *,
    refresh: bool = False,
    pause: float = 0.0,
    sleep: Callable[[float], None] = time.sleep,
    on_result: Callable[[QuestionRun], None] | None = None,
) -> list[QuestionRun]:
    """Answer every question. A provider failure is recorded and the run goes on.

    Answers are saved after each call, so a run stopped by a quota keeps what it obtained.
    `pause` waits between two real calls (never for an answer found in the cache).
    """
    runs = []
    for question in questions:
        key = config.cache_key(question.question)
        found = None if refresh else cache.get(key)
        if found is not None:
            run = QuestionRun(question, found[0], None, found[1], cached=True)
        else:
            started = time.perf_counter()
            try:
                answer = answerer.answer(question.question)
            except LLMError as error:
                seconds = time.perf_counter() - started
                run = QuestionRun(question, None, str(error), seconds, cached=False)
            else:
                seconds = time.perf_counter() - started
                cache.put(key, answer, seconds)
                cache.save()
                run = QuestionRun(question, answer, None, seconds, cached=False)
            if pause > 0:
                sleep(pause)
        runs.append(run)
        if on_result is not None:
            on_result(run)
    return runs
