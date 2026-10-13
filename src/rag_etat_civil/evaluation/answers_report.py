"""Write the answer evaluation as a Markdown report (in French, like the project's docs)."""

from __future__ import annotations

import statistics
from collections.abc import Sequence

from rag_etat_civil.answering.models import RefusalReason
from rag_etat_civil.evaluation.answers import Verdict, count_verdicts
from rag_etat_civil.evaluation.answers_run import QuestionRun, RunConfig

Results = Sequence[tuple[RunConfig, Sequence[QuestionRun]]]

LABELS = {
    Verdict.OK: "OK",
    Verdict.PARTIAL: "partiel",
    Verdict.REVIEW: "à relire",
    Verdict.TOLERATED: "toléré",
    Verdict.FAILED: "ÉCHEC",
    Verdict.ERROR: "erreur",
}
NO_LANGUAGE_MODEL = (RefusalReason.OUT_OF_SCOPE, RefusalReason.NO_PASSAGE)


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return lines


def _numbers(values: Sequence[int]) -> str:
    return ", ".join(map(str, values)) or "-"


def _median_seconds(runs: Sequence[QuestionRun]) -> str:
    """Time of the answers that went through the language model."""
    times = [
        r.seconds for r in runs if r.answer is not None and r.answer.reason not in NO_LANGUAGE_MODEL
    ]
    return f"{statistics.median(times):.1f} s" if times else "-"


def _comparison(results: Results) -> list[str]:
    rows = []
    for config, runs in results:
        counts = count_verdicts(r.score for r in runs)
        rows.append(
            [
                config.label,
                *(str(counts[verdict]) for verdict in LABELS),
                _median_seconds(runs),
            ]
        )
    return _table(["configuration", *LABELS.values(), "durée médiane"], rows)


def _by_category(runs: Sequence[QuestionRun]) -> list[str]:
    categories = list(dict.fromkeys(r.question.category for r in runs))
    rows = []
    for category in categories:
        counts = count_verdicts(r.score for r in runs if r.question.category == category)
        rows.append([category, *(str(counts[v]) for v in LABELS)])
    return _table(["catégorie", *LABELS.values()], rows)


def _problems(run: QuestionRun) -> list[str]:
    score = run.score
    lines = []
    if run.error:
        lines.append(f"- Erreur du modèle de langage : {run.error}")
    if run.answer is not None and run.answer.reason is not None:
        lines.append(f"- Refus : `{run.answer.reason.value}`")
    if score.missing_facts:
        facts = " ; ".join(" / ".join(group) for group in score.missing_facts)
        lines.append(f"- Faits manquants : {facts}")
    if score.missing_citations:
        lines.append(f"- Articles attendus non cités : {_numbers(score.missing_citations)}")
    if score.unexpected_citations:
        extra = _numbers(score.unexpected_citations)
        lines.append(f"- Articles cités hors liste (à relire) : {extra}")
    if score.forbidden_hits:
        lines.append(f"- Motifs interdits trouvés : {', '.join(score.forbidden_hits)}")
    return lines


def _answer_block(config: RunConfig, run: QuestionRun) -> list[str]:
    cited = _numbers([c.article for c in run.answer.citations]) if run.answer else "-"
    summary = f"{config.label} : {LABELS[run.score.verdict]} (articles cités : {cited}, "
    summary += f"{run.seconds:.1f} s{', en cache' if run.cached else ''})"
    text = run.answer.text if run.answer else "(pas de réponse)"
    return [
        "<details>",
        f"<summary>{summary}</summary>",
        "",
        text,
        "",
        *_problems(run),
        "</details>",
        "",
    ]


def render_answers_report(results: Results) -> str:
    first_config, first_runs = results[0]
    lines = [
        "# Évaluation des réponses",
        "",
        "Rapport généré par `make eval-answers`. Chaque question est posée à l'assistant complet "
        "(recherche, modèle de langage, vérification des citations) puis notée automatiquement. "
        "La note est un indicateur : les réponses complètes sont données plus bas pour relecture.",
        "",
        f"Modèle de langage : `{first_config.model_id}` · {len(first_runs)} questions",
        "",
        "## Comparaison des configurations",
        "",
        "OK : bon statut, tous les faits et tous les articles attendus cités. Partiel : bon "
        "statut mais il manque un fait ou un article. À relire : réponse complète "
        "mais citant un article que personne n'a listé ; un humain vérifie s'il est pertinent. "
        "Toléré : autre statut acceptable (refus propre sur un cas limite). ÉCHEC : mauvais "
        "statut ou motif interdit. Erreur : le modèle de langage n'a pas répondu.",
        "",
        *_comparison(results),
        "",
    ]
    for config, runs in results:
        lines += [f"## Par catégorie : {config.label}", "", *_by_category(runs), ""]

    lines += ["## Verdict par question", ""]
    rows = []
    for index, run in enumerate(first_runs):
        rows.append(
            [
                run.question.id,
                run.question.category,
                *(LABELS[runs[index].score.verdict] for _, runs in results),
            ]
        )
    lines += _table(["id", "catégorie", *(config.label for config, _ in results)], rows)

    lines += ["", "## Réponses", ""]
    for index, run in enumerate(first_runs):
        question = run.question
        lines += [
            f"### {question.id} · {question.category}",
            "",
            f"**Question :** {question.question}",
            "",
            f"**Attendu :** {question.expected_status}"
            + (
                f" · articles {_numbers(question.expected_articles)}"
                if question.expected_articles
                else ""
            ),
            "",
            f"> **Référence :** {question.reference_answer}",
            "",
        ]
        for config, runs in results:
            lines += _answer_block(config, runs[index])
    return "\n".join(lines).rstrip() + "\n"
