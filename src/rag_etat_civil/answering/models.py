"""Types of the answering step.

Two different things live here:
- `ModelAnswer` is what we ask the language model to produce (and then check);
- `Answer` is what the application returns to its users.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

REFUSAL_MESSAGE = "Je ne trouve pas la réponse dans le texte de la loi."


class ModelAnswer(BaseModel):
    """The JSON the language model must return."""

    status: Literal["answered", "refused"] = Field(
        description='"answered" if the passages contain the answer, "refused" if they do not'
    )
    answer: str = Field(description="The answer in French, mentioning the article numbers")
    citations: list[int] = Field(
        description="Numbers of the articles the answer relies on (only articles of the passages)"
    )


class RefusalReason(StrEnum):
    NO_PASSAGE = "no_passage"  # the search found nothing
    OUT_OF_SCOPE = "out_of_scope"  # the best passage is too far from the question
    MODEL_REFUSED = "model_refused"  # the model judged that the passages do not answer
    INVALID_ANSWER = "invalid_answer"  # the model's answer could not be trusted


class Citation(BaseModel):
    """An article the answer relies on, with where to check it in the official PDF."""

    article: int
    page: int


class Answer(BaseModel):
    """What the application returns for a question."""

    status: Literal["answered", "refused"]
    text: str
    citations: list[Citation] = []
    reason: RefusalReason | None = None  # set when status is "refused"
