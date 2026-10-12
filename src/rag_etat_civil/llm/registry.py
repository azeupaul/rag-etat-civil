"""Choose the language model provider from the settings (LLM_PROVIDER variable).

To add a provider: write a class that extends `LLMProvider`, then add one line below.
"""

from __future__ import annotations

from collections.abc import Callable

from rag_etat_civil.config import Settings
from rag_etat_civil.llm.base import LLMProvider

# No provider is registered yet: the first one (Gemini) is added with its own class.
LLM_PROVIDERS: dict[str, Callable[[Settings], LLMProvider]] = {}


def create_llm(settings: Settings) -> LLMProvider:
    try:
        factory = LLM_PROVIDERS[settings.llm_provider]
    except KeyError:
        raise ValueError(
            f"Unknown LLM_PROVIDER {settings.llm_provider!r}. Available: {sorted(LLM_PROVIDERS)}"
        ) from None
    return factory(settings)
