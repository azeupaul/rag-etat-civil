"""Google Gemini as a language model provider.

Needs the optional dependency: `uv sync --extra gemini`.
"""

from __future__ import annotations

from typing import Any

from google import genai
from google.genai import errors, types

from rag_etat_civil.llm.base import LLMError, LLMProvider


class GeminiProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        timeout_seconds: float = 30.0,
        client: Any = None,
    ) -> None:
        self._model = model
        self._timeout_ms = int(timeout_seconds * 1000)  # the SDK counts in milliseconds
        # `client` can be replaced in tests, to avoid any network call.
        self._client = client or genai.Client(api_key=api_key)

    @property
    def model_id(self) -> str:
        return f"gemini:{self._model}"

    def generate_json(self, system_prompt: str, user_prompt: str, schema: dict[str, Any]) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.0,
            response_mime_type="application/json",
            response_json_schema=schema,
            http_options=types.HttpOptions(timeout=self._timeout_ms),
        )
        try:
            response = self._client.models.generate_content(
                model=self._model, contents=user_prompt, config=config
            )
        except errors.APIError as error:
            raise LLMError(f"Gemini request failed: {error}") from error
        except Exception as error:  # network, timeout... the SDK does not wrap them all
            raise LLMError(f"Gemini request failed: {error!r}") from error

        text = response.text
        if not text:
            raise LLMError("Gemini returned no text (the answer may have been blocked).")
        return text
