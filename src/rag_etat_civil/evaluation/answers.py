"""Score an answer of the assistant against the reference question it was asked.

The score is an indicator, not a judge: it checks what a program can check (status, facts,
citations, forbidden content). The report also shows the full answers for a human to read.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from rag_etat_civil.answering.models import Answer
from rag_etat_civil.evaluation.dataset import EvalQuestion


class Verdict(StrEnum):
    OK = "ok"  # right status; every fact and every expected article is there
    PARTIAL = "partial"  # right status, but a fact or an expected article is missing
    TOLERATED = "tolerated"  # another acceptable status (e.g. a clean refusal on a limit case)
    FAILED = "failed"  # wrong status, forbidden content, or an article outside the expectation
    ERROR = "error"  # the language model could not be reached: nothing to judge


@dataclass(frozen=True, slots=True)
class AnswerScore:
    verdict: Verdict
    missing_facts: tuple[tuple[str, ...], ...] = ()  # groups of spellings none of which appears
    missing_citations: tuple[int, ...] = ()  # expected articles the answer does not cite
    # Cited articles that are neither expected nor accepted.
    unexpected_citations: tuple[int, ...] = ()
    forbidden_hits: tuple[str, ...] = ()  # forbidden patterns found in the text


CURLY_APOSTROPHE = chr(0x2019)  # word processors and models write this one


def _normalize(text: str) -> str:
    text = text.casefold().replace(CURLY_APOSTROPHE, "'")
    return " ".join(text.split())  # also turns non-breaking spaces into plain ones


def fact_present(variants: Iterable[str], text: str) -> bool:
    """One of the spellings appears as whole words ("90" is not found in "190")."""
    haystack = _normalize(text)
    return any(
        re.search(rf"(?<!\w){re.escape(_normalize(variant))}(?!\w)", haystack)
        for variant in variants
    )


def score_answer(question: EvalQuestion, answer: Answer) -> AnswerScore:
    cited = tuple(dict.fromkeys(citation.article for citation in answer.citations))
    unexpected = tuple(a for a in cited if a not in question.accepted_articles)
    forbidden = tuple(
        pattern
        for pattern in question.forbidden_patterns
        if re.search(pattern, answer.text, re.IGNORECASE)
    )
    as_expected = answer.status == question.expected_status
    tolerated = not as_expected and answer.status == question.tolerated_status

    if unexpected or forbidden or not (as_expected or tolerated):
        return AnswerScore(Verdict.FAILED, (), (), unexpected, forbidden)
    if tolerated:
        return AnswerScore(Verdict.TOLERATED)
    if question.expected_status == "refused":
        return AnswerScore(Verdict.OK)

    missing_facts = tuple(
        tuple(group) for group in question.facts if not fact_present(group, answer.text)
    )
    missing_citations = tuple(a for a in question.expected_articles if a not in cited)
    if missing_facts or missing_citations:
        return AnswerScore(Verdict.PARTIAL, missing_facts, missing_citations)
    return AnswerScore(Verdict.OK)


def count_verdicts(scores: Iterable[AnswerScore]) -> Counter[Verdict]:
    return Counter(score.verdict for score in scores)
