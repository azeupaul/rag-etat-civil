"""Prepare French text for keyword search (BM25).

Questions and passages go through the same steps, so that "déclarer", "déclaration" and
"déclarée" end up as the same token:

1. lowercase and split into words and numbers (the apostrophe separates "l'article");
2. drop very common words ("de", "la", "pour"...), which say nothing about the topic;
3. reduce each word to its stem with the French Snowball stemmer ("déclarée" -> "déclar");
4. remove the accents of the stem, so that every token is plain ASCII ("décès" -> "deces").

The stemmer must see the accents: without them it gets "déclarée" wrong ("declare") and
turns "décès" into "dec".

Known limitation: a question typed without accents ("delai", "deces") can miss the words
that the stemmer shortens differently without accents. The embeddings are not affected, which
is one more reason for the hybrid search. The evaluation will tell whether it matters.
"""

from __future__ import annotations

import re
import unicodedata

from py_rust_stemmers import SnowballStemmer

_WORD_RE = re.compile(r"[^\W_]+")  # letters (accented or not) and digits
_STEMMER = SnowballStemmer("french")

# Function words only, written without accents. Words that carry legal meaning (ne, pas,
# sans, non, peut, doit...) are deliberately kept.
STOPWORDS = frozenset(
    """
    a au aux avec ce ces cet cette ceux celle celles dans de des du d elle elles en et il ils
    je la le les leur leurs l lui ma mes mon ta tes ton sa ses son notre nos votre vos nous
    vous me te se y on ou ni mais donc or car que qui quoi dont ou quel quelle quels quelles
    par pour sur sous chez vers entre comme si un une uns unes est sont etait ete etre
    ont ai as avons avez qu n s c j m t
    """.split()  # noqa: SIM905 - a word list reads better as one block of text
)


def fold_accents(text: str) -> str:
    """Lowercase and remove accents: "Déclarée" -> "declaree"."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def tokenize(text: str) -> list[str]:
    """Words of `text` as search tokens (see the module docstring for the steps)."""
    words = _WORD_RE.findall(text.lower())
    return [
        fold_accents(_STEMMER.stem_word(word))
        for word in words
        if fold_accents(word) not in STOPWORDS
    ]
