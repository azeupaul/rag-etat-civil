"""Reciprocal Rank Fusion (RRF): merge several rankings into one.

The vector search and BM25 give scores on different scales (a cosine similarity around 0.8,
a BM25 score around 6), so their scores cannot be added. RRF ignores the scores and only
uses the *rank* of each passage in each list:

    score(passage) = sum, over the lists that contain it, of 1 / (k + rank)

A passage ranked high in several lists wins; a passage found by only one method is kept.
The constant k (60 in the original paper) softens the gap between the first ranks, so that
being 1st rather than 2nd matters less than being in two lists rather than one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import NamedTuple

DEFAULT_K = 60


class Fused(NamedTuple):
    """A passage after fusion: its id, its RRF score and which rankings contained it."""

    id: str
    score: float
    sources: tuple[str, ...]


def reciprocal_rank_fusion(
    rankings: Mapping[str, Sequence[str]], *, k: int = DEFAULT_K
) -> list[Fused]:
    """Merge rankings (name -> ids, best first) into one list, best first.

    Ties keep the order in which the passages were first seen, so results are reproducible.
    """
    if k <= 0:
        raise ValueError("k must be positive")

    scores: dict[str, float] = {}
    sources: dict[str, list[str]] = {}
    for name, ids in rankings.items():
        seen: set[str] = set()
        rank = 0
        for chunk_id in ids:
            if chunk_id in seen:  # a passage counts once per ranking
                continue
            seen.add(chunk_id)
            rank += 1
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
            sources.setdefault(chunk_id, []).append(name)

    ordered = sorted(scores, key=lambda chunk_id: -scores[chunk_id])  # sorted() is stable
    return [Fused(chunk_id, scores[chunk_id], tuple(sources[chunk_id])) for chunk_id in ordered]
