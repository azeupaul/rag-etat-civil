"""Tests for the Gemini adapter, with a fake client (no network, no API key)."""

import os

import pytest

pytest.importorskip("google.genai", reason="needs `uv sync --extra gemini`")

from google.genai import errors

from rag_etat_civil.config import Settings
from rag_etat_civil.llm.base import LLMError
from rag_etat_civil.llm.gemini import GeminiProvider
from rag_etat_civil.llm.registry import create_llm

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}}


class FakeModels:
    def __init__(self, text: str | None = '{"ok": true}', error: Exception | None = None):
        self.text = text
        self.error = error
        self.calls: list[dict] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return type("Response", (), {"text": self.text})()


class FakeClient:
    def __init__(self, models: FakeModels) -> None:
        self.models = models


def provider_with(models: FakeModels, **options) -> GeminiProvider:
    return GeminiProvider("key", "gemini-test", client=FakeClient(models), **options)


def test_the_request_asks_for_json_with_the_schema_and_no_randomness():
    models = FakeModels()

    result = provider_with(models, timeout_seconds=12).generate_json("system", "user", SCHEMA)

    assert result == '{"ok": true}'
    call = models.calls[0]
    assert call["model"] == "gemini-test"
    assert call["contents"] == "user"
    config = call["config"]
    assert config.system_instruction == "system"
    assert config.temperature == 0.0
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == SCHEMA
    assert config.http_options.timeout == 12_000  # milliseconds


def test_model_id_includes_the_provider_and_the_model():
    assert provider_with(FakeModels()).model_id == "gemini:gemini-test"


def test_an_api_error_becomes_an_llm_error():
    error = errors.APIError(429, {"error": {"message": "quota exceeded"}})

    with pytest.raises(LLMError, match="quota exceeded"):
        provider_with(FakeModels(error=error)).generate_json("s", "u", SCHEMA)


def test_a_network_failure_becomes_an_llm_error():
    with pytest.raises(LLMError, match="timed out"):
        provider_with(FakeModels(error=TimeoutError("timed out"))).generate_json("s", "u", SCHEMA)


@pytest.mark.parametrize("text", [None, ""])
def test_an_empty_reply_becomes_an_llm_error(text):
    with pytest.raises(LLMError, match="no text"):
        provider_with(FakeModels(text=text)).generate_json("s", "u", SCHEMA)


def test_the_registry_creates_gemini_from_the_settings():
    llm = create_llm(Settings(gemini_api_key="key", gemini_model="gemini-x"))
    assert llm.model_id == "gemini:gemini-x"


def test_the_registry_explains_a_missing_api_key():
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        create_llm(Settings(gemini_api_key=""))


@pytest.mark.llm
@pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY"), reason="GEMINI_API_KEY is not set")
def test_real_gemini_returns_json_matching_the_schema():
    import json

    from dotenv import load_dotenv

    load_dotenv()
    llm = create_llm(Settings.from_env())

    text = llm.generate_json(
        "Réponds uniquement par un objet JSON conforme au schéma.",
        "Le ciel est-il bleu par temps clair ?",
        SCHEMA,
    )

    assert isinstance(json.loads(text)["ok"], bool)
