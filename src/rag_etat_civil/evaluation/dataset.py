"""The reference questions used to evaluate the assistant (`eval/questions.json`)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_QUESTIONS_PATH = Path(__file__).resolve().parents[3] / "eval" / "questions.json"

Category = Literal[
    "direct",
    "cascade",
    "colloquial",
    "lookup",
    "limit",
    "variant",
    "out_of_law",
    "off_topic",
    "adversarial",
]
Status = Literal["answered", "refused"]


class EvalQuestion(BaseModel):
    """One reference question, with what a good answer contains and what it must not contain."""

    model_config = ConfigDict(extra="forbid")

    id: str
    category: Category
    question: str = Field(min_length=1)
    expected_status: Status
    # Another status that is acceptable but counted apart (e.g. a clean refusal on a limit case).
    tolerated_status: Status | None = None
    # Articles an ideal answer relies on, and articles that are also fine to cite.
    expected_articles: list[int]
    also_accepted_articles: list[int]
    # Each group lists alternative spellings of one fact; one spelling per group must appear.
    facts: list[list[str]]
    # Regular expressions that must not match the answer (invented content, injected text).
    forbidden_patterns: list[str]
    reference_answer: str = Field(min_length=1)
    note: str | None

    @model_validator(mode="after")
    def _check_consistency(self) -> EvalQuestion:
        for pattern in self.forbidden_patterns:
            try:
                re.compile(pattern)
            except re.error as error:
                raise ValueError(f"{self.id}: invalid pattern {pattern!r} ({error})") from error
        if self.expected_status == "answered" and not self.expected_articles:
            raise ValueError(f"{self.id}: an answerable question needs expected articles")
        if self.expected_status == "refused" and self.expected_articles:
            raise ValueError(f"{self.id}: a question to refuse has no expected articles")
        return self

    @property
    def accepted_articles(self) -> set[int]:
        """Every article an answer may cite without being wrong."""
        return set(self.expected_articles) | set(self.also_accepted_articles)


def load_questions(path: Path = DEFAULT_QUESTIONS_PATH) -> list[EvalQuestion]:
    questions = [EvalQuestion.model_validate(raw) for raw in json.loads(path.read_text("utf-8"))]
    ids = [q.id for q in questions]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate question ids in " + str(path))
    return questions
