"""Ask a question to the whole pipeline from the command line.

    make ask q="dans quel délai déclarer une naissance ?"

Needs the index (`make index`) and a language model configured in .env.
"""

from __future__ import annotations

import argparse
import textwrap
import time
from collections.abc import Sequence

from rag_etat_civil.answering.factory import load_answerer
from rag_etat_civil.answering.models import Answer
from rag_etat_civil.config import Settings
from rag_etat_civil.llm.base import LLMError
from rag_etat_civil.retrieval.factory import IndexNotBuiltError


def format_answer(answer: Answer) -> str:
    lines = [textwrap.fill(answer.text, width=96)]
    if answer.citations:
        lines.append("")
        lines.append("Articles cités :")
        lines.extend(f"  - article {c.article} (PDF p. {c.page})" for c in answer.citations)
    if answer.reason:
        lines.append("")
        lines.append(f"[refus : {answer.reason.value}]")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ask a question about the law.")
    parser.add_argument("question", nargs="+", help="the question, in French")
    question = " ".join(parser.parse_args(argv).question)

    try:
        answerer = load_answerer(Settings.from_env())
    except (IndexNotBuiltError, ValueError) as error:
        print(error)
        return 1

    started = time.perf_counter()
    try:
        answer = answerer.answer(question)
    except LLMError as error:
        print(f"The language model could not answer: {error}")
        return 2
    elapsed = time.perf_counter() - started

    print(f"Question: {question}\n")
    print(format_answer(answer))
    print(f"\n({elapsed:.1f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
