"""Detect article numbers written in a question ("article 36", "art. 10 et 11", "1er").

When someone asks about a given article, search is not needed: we know which one they want.
"""

from __future__ import annotations

import re

_NUMBER = r"(?:\d{1,3}(?:er)?\b|premier\b)"
_ARTICLE_LIST_RE = re.compile(
    rf"\b(?:articles?|art)\b\.?\s*(?P<numbers>{_NUMBER}(?:\s*(?:,|et|ou|&)\s*{_NUMBER})*)",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"\d{1,3}|premier", re.IGNORECASE)


def find_article_numbers(question: str, max_article: int) -> list[int]:
    """Article numbers mentioned in the question, in order, without duplicates.

    Numbers outside 1..max_article are ignored (the law has no article 0 or 500).
    Ranges such as "articles 36 à 40" are not expanded.
    """
    found: list[int] = []
    for match in _ARTICLE_LIST_RE.finditer(question):
        for token in _NUMBER_RE.findall(match.group("numbers")):
            number = 1 if token.lower() == "premier" else int(token)
            if 1 <= number <= max_article and number not in found:
                found.append(number)
    return found
