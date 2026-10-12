"""Write the retrieval measurements as a Markdown report (in French, like the project's docs)."""

from __future__ import annotations

from collections.abc import Sequence

from rag_etat_civil.evaluation.retrieval import (
    QuestionRetrieval,
    SimilarityAnalysis,
    analyse_similarity,
    recommend_top_k,
)

QUESTION_CHARS = 48


def _cell(result: QuestionRetrieval, k: int) -> str:
    score = result.scores[k]
    if score.complete is None:
        return "-"
    return "✓" if score.complete else f"{len(score.found)}/{len(score.expected)}"


def _short(text: str) -> str:
    return text if len(text) <= QUESTION_CHARS else text[: QUESTION_CHARS - 1].rstrip() + "…"


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return lines


def _by_category(results: Sequence[QuestionRetrieval], ks: Sequence[int]) -> list[str]:
    """For each category, how many answerable questions get all their articles, per top_k."""
    answerable = [r for r in results if r.question.expected_articles]
    categories = list(dict.fromkeys(r.question.category for r in answerable))
    rows = []
    for label, group in [
        (c, [r for r in answerable if r.question.category == c]) for c in categories
    ]:
        rows.append(
            [label, *(f"{sum(bool(r.scores[k].complete) for r in group)}/{len(group)}" for k in ks)]
        )
    rows.append(
        [
            "**total**",
            *(
                f"{sum(bool(r.scores[k].complete) for r in answerable)}/{len(answerable)}"
                for k in ks
            ),
        ]
    )
    return _table(["catégorie", *(f"k={k}" for k in ks)], rows)


def render_retrieval_report(
    results: Sequence[QuestionRetrieval], *, embedding_model: str, candidates: int
) -> str:
    ks = sorted(results[0].scores)
    widest = ks[-1]
    recommended = recommend_top_k(results)
    analysis = analyse_similarity(results)

    lines = [
        "# Évaluation de la recherche",
        "",
        "Rapport généré par `make eval-retrieval`. Il mesure si les articles attendus arrivent "
        "jusqu'au modèle de langage, sans appeler celui-ci.",
        "",
        f"Modèle d'embedding : `{embedding_model}` · candidats par méthode : {candidates} · "
        f"valeurs de top_k testées : {', '.join(map(str, ks))}",
        "",
        "## Articles attendus trouvés, par catégorie",
        "",
        "Nombre de questions pour lesquelles **tous** les articles attendus figurent parmi "
        "les passages donnés au modèle.",
        "",
        *_by_category(results, ks),
        "",
    ]
    if recommended is None:
        lines += ["**Aucune valeur testée ne donne tous les articles des questions en cascade.**"]
    else:
        lines += [
            f"**top_k recommandé : {recommended}**, la plus petite valeur testée qui donne tous "
            "les articles attendus des questions en cascade."
        ]

    lines += ["", "## Détail par question", ""]
    lines += [
        "Cellule : ✓ tous les articles attendus sont présents, sinon `trouvés/attendus`. "
        f"Le rang et les articles manquants sont donnés pour k={widest}.",
        "",
    ]
    rows = []
    for r in results:
        score = r.scores[widest]
        rows.append(
            [
                r.question.id,
                r.question.category,
                ", ".join(map(str, r.question.expected_articles)) or "-",
                *(_cell(r, k) for k in ks),
                str(score.first_rank) if score.first_rank else "-",
                ", ".join(map(str, score.missing)) or "-",
            ]
        )
    lines += _table(
        ["id", "catégorie", "attendus", *(f"k={k}" for k in ks), "rang", "manquants"], rows
    )

    lines += ["", "## Similarité et seuil de refus", ""]
    lines += [
        "Meilleur cosinus entre la question et les passages trouvés. Les questions qui "
        "nomment un article sont exclues du calcul : le seuil ne s'y applique jamais.",
        "",
    ]
    sim_rows = [
        [
            r.question.id,
            _short(r.question.question),
            r.question.expected_status
            + (" (toléré : refus)" if r.question.tolerated_status == "refused" else ""),
            f"{r.best_similarity:.3f}",
            "article nommé" if r.named else "",
        ]
        for r in sorted(results, key=lambda r: r.best_similarity or 0.0, reverse=True)
        if r.best_similarity is not None
    ]
    lines += _table(["id", "question", "statut attendu", "cosinus", ""], sim_rows)
    lines += ["", *_threshold_conclusion(analysis)]
    return "\n".join(lines) + "\n"


def _threshold_conclusion(analysis: SimilarityAnalysis) -> list[str]:
    low, high = analysis.lowest_answerable, analysis.highest_refused
    if analysis.threshold is not None and low and high:
        return [
            f"Les deux groupes sont séparés : la question à répondre la plus basse est {low.id} "
            f"({low.similarity:.3f}) et la question à refuser la plus haute est {high.id} "
            f"({high.similarity:.3f}). Seuil possible : **MIN_SIMILARITY={analysis.threshold}**."
        ]
    lines = [
        "Les deux groupes se chevauchent (ou l'un est vide) : aucun seuil ne les sépare "
        "proprement. Garder `MIN_SIMILARITY=0` et laisser le modèle refuser."
    ]
    if low and high:
        lines += [
            "",
            f"Question à répondre la plus basse : {low.id} ({low.similarity:.3f}). "
            f"Question à refuser la plus haute : {high.id} ({high.similarity:.3f}).",
        ]
    return lines
