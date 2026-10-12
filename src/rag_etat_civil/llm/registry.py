"""Choose the language model provider from the settings (LLM_PROVIDER variable).

To add a provider: write a class that extends `LLMProvider`, then add one line below.
"""

from __future__ import annotations

from collections.abc import Callable

from rag_etat_civil.config import Settings
from rag_etat_civil.llm.base import LLMProvider


def _gemini(settings: Settings) -> LLMProvider:
    # Imported here so that the application starts without the optional Gemini dependency.
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not set. Put it in your .env file.")
    try:
        from rag_etat_civil.llm.gemini import GeminiProvider
    except ImportError as error:
        raise ValueError(
            "The Gemini provider needs an optional dependency: run `uv sync --extra gemini`."
        ) from error

    return GeminiProvider(
        settings.gemini_api_key,
        settings.gemini_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )


LLM_PROVIDERS: dict[str, Callable[[Settings], LLMProvider]] = {
    "gemini": _gemini,
}


def create_llm(settings: Settings) -> LLMProvider:
    try:
        factory = LLM_PROVIDERS[settings.llm_provider]
    except KeyError:
        raise ValueError(
            f"Unknown LLM_PROVIDER {settings.llm_provider!r}. Available: {sorted(LLM_PROVIDERS)}"
        ) from None
    return factory(settings)
