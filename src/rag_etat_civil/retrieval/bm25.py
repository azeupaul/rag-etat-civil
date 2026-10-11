"""BM25: rank passages by the words they share with the question.

For every word of the question found in a passage, BM25 adds up:

    idf(word) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * length / average_length))

- idf: rare words weigh more than common ones;
- tf: how often the word appears in the passage, with diminishing returns (k1);
- length: a match in a short passage is worth more than in a long one (b).
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable, Sequence

from rag_etat_civil.retrieval.text import tokenize
from rag_etat_civil.retrieval.vector_index import Match

Tokenizer = Callable[[str], list[str]]


class BM25:
    def __init__(
        self,
        ids: Sequence[str],
        texts: Sequence[str],
        *,
        k1: float = 1.5,
        b: float = 0.75,
        tokenizer: Tokenizer = tokenize,
    ) -> None:
        if len(ids) != len(texts):
            raise ValueError("Expected one text per id")
        self._ids = list(ids)
        self._k1 = k1
        self._b = b
        self._tokenizer = tokenizer

        documents = [tokenizer(text) for text in texts]
        self._lengths = [len(tokens) for tokens in documents]
        self._average_length = sum(self._lengths) / len(documents) if documents else 0.0

        # postings[word] = [(position of the passage, occurrences of the word in it), ...]
        self._postings: dict[str, list[tuple[int, int]]] = {}
        for position, tokens in enumerate(documents):
            for word, count in Counter(tokens).items():
                self._postings.setdefault(word, []).append((position, count))

        n = len(documents)
        self._idf = {
            word: math.log(1 + (n - len(postings) + 0.5) / (len(postings) + 0.5))
            for word, postings in self._postings.items()
        }

    def search(self, query: str, k: int) -> list[Match]:
        """Return the `k` best passages, best first. Passages sharing no word are left out."""
        scores: dict[int, float] = {}
        for word in set(self._tokenizer(query)):
            idf = self._idf.get(word)
            if idf is None:  # the word does not appear anywhere in the corpus
                continue
            for position, tf in self._postings[word]:
                length_ratio = self._lengths[position] / self._average_length
                norm = self._k1 * (1 - self._b + self._b * length_ratio)
                contribution = idf * tf * (self._k1 + 1) / (tf + norm)
                scores[position] = scores.get(position, 0.0) + contribution
        # Ties keep the order of the corpus, so results are reproducible.
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:k]
        return [Match(self._ids[position], score) for position, score in ranked]
