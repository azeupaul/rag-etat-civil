"""Evaluate the assistant against the reference questions.

    make eval-retrieval

`retrieval` checks the search alone (no language model): do the expected articles reach the
model, for which top_k, and can a similarity threshold tell off-topic questions apart?
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from rag_etat_civil.config import Settings
from rag_etat_civil.evaluation.dataset import load_questions
from rag_etat_civil.evaluation.retrieval import evaluate_retrieval
from rag_etat_civil.evaluation.retrieval_report import render_retrieval_report
from rag_etat_civil.retrieval.factory import IndexNotBuiltError, load_retriever

RESULTS_DIR = Path(__file__).resolve().parent / "results"
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

    args = parser.parse_args(argv)
    return run_retrieval(args.ks, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
