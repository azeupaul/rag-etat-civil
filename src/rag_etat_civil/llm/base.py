"""The contract every language model provider must respect."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMError(RuntimeError):
    """The provider could not produce an answer (network, quota, refused request...).

    Each implementation wraps its own library errors in this one, so the rest of the
    application does not depend on any provider's SDK.
    """


class LLMProvider(ABC):
    """Asks a language model for a JSON answer.

    The interface is deliberately small. How a provider is told to answer in JSON differs
    from one to the next; that detail stays inside each implementation.
    """

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Unique name of the model used (e.g. "gemini:gemini-3.5-flash-lite")."""

    @abstractmethod
    def generate_json(self, system_prompt: str, user_prompt: str, schema: dict[str, Any]) -> str:
        """Return the model's answer as JSON text matching `schema` (a JSON Schema).

        The text is not guaranteed to be meaningful, only to be asked for in that shape:
        callers must parse and validate it. Raises `LLMError` when the provider fails.
        """
