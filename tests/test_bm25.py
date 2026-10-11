import json
from pathlib import Path

import pytest

from rag_etat_civil.retrieval.bm25 import BM25
from rag_etat_civil.retrieval.vector_index import Match

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# A toy corpus where the numbers can be checked by hand. `str.split` replaces the French
# tokenizer so that "a", "b" and "c" stay exactly as written.
#   d1 = a a b (3 words)   d2 = b c (2 words)   d3 = c c c c (4 words)   average length = 3
IDS = ["d1", "d2", "d3"]
TEXTS = ["a a b", "b c", "c c c c"]


@pytest.fixture
def toy():
    return BM25(IDS, TEXTS, tokenizer=str.split)


def test_hand_computed_score(toy):
    # "a" is in 1 passage out of 3: idf = ln(1 + (3 - 1 + 0.5) / (1 + 0.5)) = 0.9808
    # in d1: tf = 2, length 3 = average, so the length factor is 1:
    #   2 * 2.5 / (2 + 1.5) = 1.4286   ->   0.9808 * 1.4286 = 1.4012
    matches = toy.search("a", k=5)
    assert matches == [Match("d1", pytest.approx(1.4012, abs=1e-3))]


def test_shorter_passage_scores_higher_for_the_same_word(toy):
    # "b" appears once in d1 (3 words) and once in d2 (2 words).
    # idf = ln(1 + (3 - 2 + 0.5) / (2 + 0.5)) = 0.47
    #   d1: 0.47 * 2.5 / (1 + 1.5 * 1)           = 0.4700
    #   d2: 0.47 * 2.5 / (1 + 1.5 * (0.25 + 0.5)) = 0.5529
    scores = {m.id: m.score for m in toy.search("b", k=5)}
    assert scores["d1"] == pytest.approx(0.4700, abs=1e-3)
    assert scores["d2"] == pytest.approx(0.5529, abs=1e-3)


def test_repeating_a_word_has_diminishing_returns():
    many = BM25(["once", "ten", "other"], ["x", " ".join(["x"] * 10), "y"], tokenizer=str.split)
    scores = {m.id: m.score for m in many.search("x", k=3)}
    assert scores["ten"] > scores["once"]
    assert scores["ten"] < 10 * scores["once"]


def test_rare_word_outweighs_common_word():
    corpus = BM25(
        ["p1", "p2", "p3", "p4"],
        ["rare common", "common", "common", "common"],
        tokenizer=str.split,
    )
    assert corpus.search("rare common", k=4)[0].id == "p1"
    assert corpus.search("common rare", k=4)[0].id == "p1"


def test_passages_without_any_query_word_are_left_out(toy):
    assert {m.id for m in toy.search("c", k=5)} == {"d2", "d3"}  # d1 has no "c"
    assert toy.search("zzz", k=5) == []
    assert toy.search("", k=5) == []


def test_k_limits_the_results(toy):
    assert len(toy.search("b c", k=1)) == 1


def test_one_text_per_id():
    with pytest.raises(ValueError, match="one text per id"):
        BM25(["only"], ["a", "b"])


def test_empty_corpus_is_allowed():
    assert BM25([], []).search("naissance", k=3) == []


# --- Behaviour on the real law -------------------------------------------------------------


@pytest.fixture(scope="module")
def law():
    lines = (DATA_DIR / "processed" / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
    chunks = [json.loads(line) for line in lines]
    return BM25([c["id"] for c in chunks], [c["indexed_text"] for c in chunks])


def ids(law: BM25, question: str, k: int = 3) -> list[str]:
    return [m.id for m in law.search(question, k)]


def test_birth_declaration_delay_is_found(law):
    assert "art-010" in ids(law, "Dans quel délai faut-il déclarer une naissance ?")


def test_exact_number_is_matched(law):
    assert ids(law, "90 jours naissance", k=1) == ["art-010"]


def test_defined_term_is_found(law):
    assert "art-055" in ids(law, "jugement supplétif")


def test_article_number_in_the_question_matches_the_heading(law):
    assert ids(law, "article 36", k=1) == ["art-036"]
