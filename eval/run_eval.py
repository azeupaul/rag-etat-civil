"""Evaluate the assistant against the reference questions.

    make eval-retrieval
    make eval-answers
    make eval-answers args="--top-k 8,15 --min-similarity 0,0.823"

`retrieval` checks the search alone (no language model): do the expected articles reach the
model, for which top_k, and can a similarity threshold tell off-topic questions apart?
`answers` asks every question to the whole assistant (needs a language model in .env), scores
the answers and compares the configurations given. Answers are cached in .cache/eval/.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from rag_etat_civil.answering.answerer import Answerer
from rag_etat_civil.answering.prompt import SYSTEM_PROMPT
from rag_etat_civil.config import Settings
from rag_etat_civil.evaluation.answers_report import render_answers_report
from rag_etat_civil.evaluation.answers_run import (
    AnswerCache,
    QuestionRun,
    RunConfig,
    prompt_hash,
    run_questions,
)
from rag_etat_civil.evaluation.dataset import load_questions
from rag_etat_civil.evaluation.retrieval import evaluate_retrieval
from rag_etat_civil.evaluation.retrieval_report import render_retrieval_report
from rag_etat_civil.ingestion.build import load_articles
from rag_etat_civil.llm.registry import create_llm
from rag_etat_civil.retrieval.factory import IndexNotBuiltError, load_retriever

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "eval" / "results"
CACHE_PATH = ROOT / ".cache" / "eval" / "answers.json"
DEFAULT_KS = (5, 8, 10, 15)


def run_retrieval(ks: Sequence[int], output: Path) -> int:
    settings = Settings.from_env()
    try:
        retriever = load_retriever(settings)
    except IndexNotBuiltError as error:
        print(error)
        return 1

    questions = load_questions()
    print(f"{len(questions)} questions, top_k = {', '.join(map(str, ks))}...")
    results = evaluate_retrieval(questions, retriever, ks)
    report = render_retrieval_report(
        results,
        embedding_model=settings.embedding_model,
        candidates=settings.retrieval_candidates,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(report)
    print(f"Report written to {output}")
    return 0


def run_answers(
    top_ks: Sequence[int],
    thresholds: Sequence[float],
    *,
    refresh: bool,
    pause: float,
    cache_path: Path,
    output: Path,
) -> int:
    settings = Settings.from_env()
    try:
        retriever = load_retriever(settings)
        llm = create_llm(settings)
    except (IndexNotBuiltError, ValueError) as error:
        print(error)
        return 1
    articles = load_articles(settings.data_dir)
    questions = load_questions()
    cache = AnswerCache(cache_path)

    results = []
    for top_k in top_ks:
        for threshold in thresholds:
            config = RunConfig(
                llm.model_id, top_k, threshold, "current", prompt_hash(SYSTEM_PROMPT)
            )
            answerer = Answerer(retriever, llm, articles, min_similarity=threshold, top_k=top_k)
            print(f"\n== {config.label}")

            def show(run: QuestionRun) -> None:
                source = "cache" if run.cached else f"{run.seconds:.1f} s"
                print(f"  {run.question.id:<4} {run.score.verdict.value:<9} ({source})")

            runs = run_questions(
                questions,
                answerer,
                config,
                cache,
                refresh=refresh,
                pause=pause,
                on_result=show,
            )
            results.append((config, runs))

    report = render_answers_report(results)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"\nReport written to {output}")
    failures = sum(1 for _, runs in results for run in runs if run.error)
    if failures:
        print(f"{failures} question(s) without answer (language model error): run it again.")
        return 2
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the assistant.")
    commands = parser.add_subparsers(dest="command", required=True)

    retrieval = commands.add_parser("retrieval", help="measure the search alone")
    retrieval.add_argument(
        "--ks",
        type=lambda text: [int(part) for part in text.split(",")],
        default=list(DEFAULT_KS),
        help="top_k values to compare, separated by commas (default: 5,8,10,15)",
    )
    retrieval.add_argument("--output", type=Path, default=RESULTS_DIR / "retrieval.md")

    answers = commands.add_parser("answers", help="ask every question to the whole assistant")
    answers.add_argument(
        "--top-k",
        type=lambda text: [int(part) for part in text.split(",")],
        help="passages given to the model, separated by commas (default: RETRIEVAL_TOP_K)",
    )
    answers.add_argument(
        "--min-similarity",
        type=lambda text: [float(part) for part in text.split(",")],
        help="refusal thresholds to compare, separated by commas (default: MIN_SIMILARITY)",
    )
    answers.add_argument("--refresh", action="store_true", help="ignore the cached answers")
    answers.add_argument("--pause", type=float, default=0.0, help="seconds between two calls")
    answers.add_argument("--cache", type=Path, default=CACHE_PATH)
    answers.add_argument("--output", type=Path, default=RESULTS_DIR / "answers.md")

    args = parser.parse_args(argv)
    if args.command == "retrieval":
        return run_retrieval(args.ks, args.output)
    defaults = Settings.from_env()
    return run_answers(
        args.top_k or [defaults.retrieval_top_k],
        args.min_similarity or [defaults.min_similarity],
        refresh=args.refresh,
        pause=args.pause,
        cache_path=args.cache,
        output=args.output,
    )


if __name__ == "__main__":
    raise SystemExit(main())
