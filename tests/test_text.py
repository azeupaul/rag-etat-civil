from rag_etat_civil.retrieval.text import fold_accents, tokenize


def test_fold_accents_and_case():
    assert fold_accents("Déclarée À L'Étranger") == "declaree a l'etranger"


def test_words_of_the_same_family_share_a_token():
    tokens = {tokenize(word)[0] for word in ("déclarer", "déclaration", "déclarée", "déclarations")}
    assert tokens == {"declar"}


def test_case_is_ignored():
    assert tokenize("DÉCÈS") == tokenize("décès")


def test_deces_is_not_confused_with_other_words():
    # Stemming after removing the accents would turn "décès" into "dec".
    assert tokenize("décès") == ["deces"]


def test_common_words_are_dropped():
    assert tokenize("le délai de la déclaration") == ["del", "declar"]


def test_apostrophes_split_words():
    assert tokenize("l'officier d'état civil") == ["offici", "etat", "civil"]


def test_numbers_are_kept():
    assert "90" in tokenize("quatre-vingt-dix (90) jours")


def test_legal_negations_are_not_dropped():
    assert tokenize("ne peut pas sans autorisation")[:3] == ["ne", "peut", "pas"]
