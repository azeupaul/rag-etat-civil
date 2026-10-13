"""From a question to a cited answer, or to a refusal.

The steps, in order:
1. search the passages of the law;
2. refuse right away if the question is clearly not about the law (optional threshold);
3. ask the language model, which must answer from the passages only;
4. check the model's answer: it must cite, and only articles that were given to it.

A wrong answer is asked again once, with the problem described. If it is still wrong, we
refuse: an answer whose citations cannot be checked is worse than no answer.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import ValidationError

from rag_etat_civil.answering.models import (
    REFUSAL_MESSAGE,
    Answer,
    Citation,
    ModelAnswer,
    RefusalReason,
)
from rag_etat_civil.answering.prompt import SYSTEM_PROMPT, build_user_prompt
from rag_etat_civil.ingestion.models import Article
from rag_etat_civil.llm.base import LLMProvider
from rag_etat_civil.retrieval.retriever import HybridRetriever, RetrievalHit

MAX_ATTEMPTS = 2
ANSWER_SCHEMA = ModelAnswer.model_json_schema()


def refusal(reason: RefusalReason) -> Answer:
    return Answer(status="refused", text=REFUSAL_MESSAGE, reason=reason)


class Answerer:
    """Answers questions about the law. An `LLMError` from the provider is not caught here:
    a provider failure is not a refusal, the caller decides how to report it."""

    def __init__(
        self,
        retriever: HybridRetriever,
        llm: LLMProvider,
        articles: Sequence[Article],
        *,
        min_similarity: float = 0.0,
        top_k: int | None = None,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        self._retriever = retriever
        self._llm = llm
        self._articles = {article.number: article for article in articles}
        self._min_similarity = min_similarity
        self._top_k = top_k  # None: the retriever's own setting
        self._system_prompt = system_prompt  # the evaluation compares several

    def answer(self, question: str) -> Answer:
        question = question.strip()
        if not question:
            return refusal(RefusalReason.NO_PASSAGE)

        hits = self._retriever.retrieve(question, top_k=self._top_k)
        if not hits:
            return refusal(RefusalReason.NO_PASSAGE)
        if self._is_out_of_scope(hits):
            return refusal(RefusalReason.OUT_OF_SCOPE)

        allowed = {hit.chunk.article for hit in hits}
        problem: str | None = None
        for _ in range(MAX_ATTEMPTS):
            user_prompt = build_user_prompt(question, hits, self._articles, problem)
            raw = self._llm.generate_json(self._system_prompt, user_prompt, ANSWER_SCHEMA)
            try:
                reply = ModelAnswer.model_validate_json(raw)
            except ValidationError:
                problem = "ce n'était pas un JSON conforme au schéma."
                continue
            if reply.status == "refused":
                return refusal(RefusalReason.MODEL_REFUSED)
            problem = self._problem_with(reply, allowed)
            if problem is None:
                return self._accept(reply)
        return refusal(RefusalReason.INVALID_ANSWER)

    def _is_out_of_scope(self, hits: Sequence[RetrievalHit]) -> bool:
        """True when no article is named and even the closest passage is too far."""
        if self._min_similarity <= 0:
            return False
        if any("lookup" in hit.sources for hit in hits):
            return False  # an article asked by its number is never refused for its similarity
        best = max((hit.similarity for hit in hits if hit.similarity is not None), default=0.0)
        return best < self._min_similarity

    @staticmethod
    def _problem_with(reply: ModelAnswer, allowed: set[int]) -> str | None:
        if not reply.answer.strip():
            return "le texte de la réponse était vide."
        if not reply.citations:
            return "elle ne citait aucun article."
        unknown = sorted(set(reply.citations) - allowed)
        if unknown:
            numbers = ", ".join(str(n) for n in unknown)
            return f"elle citait des articles absents des passages fournis ({numbers})."
        return None

    def _accept(self, reply: ModelAnswer) -> Answer:
        numbers = list(dict.fromkeys(reply.citations))  # no duplicates, order kept
        citations = [Citation(article=n, page=self._articles[n].page_start) for n in numbers]
        return Answer(status="answered", text=reply.answer.strip(), citations=citations)
