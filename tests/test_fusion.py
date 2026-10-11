import pytest

from rag_etat_civil.retrieval.fusion import Fused, reciprocal_rank_fusion


def test_hand_computed_scores_and_order():
    # k = 60. Ranks start at 1.
    #   x: 1/61                = 0.01639   (first in "vector" only)
    #   y: 1/62 + 1/61         = 0.03252   (second in "vector", first in "bm25")
    #   z: 1/63 + 1/62         = 0.03200   (third in "vector", second in "bm25")
    #   w: 1/63                = 0.01587   (third in "bm25" only)
    fused = reciprocal_rank_fusion({"vector": ["x", "y", "z"], "bm25": ["y", "z", "w"]})
    assert [f.id for f in fused] == ["y", "z", "x", "w"]
    scores = {f.id: f.score for f in fused}
    assert scores["y"] == pytest.approx(0.03252, abs=1e-5)
    assert scores["z"] == pytest.approx(0.03200, abs=1e-5)
    assert scores["x"] == pytest.approx(0.01639, abs=1e-5)
    assert scores["w"] == pytest.approx(0.01587, abs=1e-5)


def test_sources_tell_which_rankings_found_each_passage():
    fused = reciprocal_rank_fusion({"vector": ["x", "y"], "bm25": ["y", "w"]})
    sources = {f.id: f.sources for f in fused}
    assert sources == {"x": ("vector",), "y": ("vector", "bm25"), "w": ("bm25",)}


def test_a_passage_found_by_two_methods_beats_two_found_by_one():
    fused = reciprocal_rank_fusion({"vector": ["a", "both"], "bm25": ["b", "both"]})
    assert fused[0].id == "both"


def test_ties_keep_the_order_of_first_appearance():
    fused = reciprocal_rank_fusion({"vector": ["a"], "bm25": ["b"]})
    assert [f.id for f in fused] == ["a", "b"]


def test_a_passage_counts_once_per_ranking():
    fused = reciprocal_rank_fusion({"vector": ["a", "a", "b"]})
    assert fused == [
        Fused("a", pytest.approx(1 / 61), ("vector",)),
        Fused("b", pytest.approx(1 / 62), ("vector",)),
    ]


def test_empty_input():
    assert reciprocal_rank_fusion({}) == []
    assert reciprocal_rank_fusion({"vector": [], "bm25": []}) == []


def test_k_must_be_positive():
    with pytest.raises(ValueError, match="positive"):
        reciprocal_rank_fusion({"vector": ["a"]}, k=0)
