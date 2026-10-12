"""Tests for the settings read from the environment."""

from pathlib import Path

import pytest

from rag_etat_civil.config import Settings

ENV_VARIABLES = {
    "APP_DEBUG": "1",
    "MAX_QUESTION_LENGTH": "123",
    "DATA_DIR": "/somewhere/data",
    "EMBEDDER": "other-embedder",
    "EMBEDDING_MODEL": "org/other-model",
    "EMBEDDING_CACHE_DIR": "/somewhere/cache",
    "RETRIEVAL_CANDIDATES": "30",
    "RETRIEVAL_TOP_K": "7",
    "MIN_SIMILARITY": "0.83",
    "LLM_PROVIDER": "other-llm",
    "LLM_TIMEOUT_SECONDS": "12.5",
    "GEMINI_MODEL": "gemini-other",
    "GEMINI_API_KEY": "secret-key",
}


def test_every_setting_can_be_overridden_by_its_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
):
    for name, value in ENV_VARIABLES.items():
        monkeypatch.setenv(name, value)

    settings = Settings.from_env()

    assert settings == Settings(
        debug=True,
        max_question_length=123,
        data_dir=Path("/somewhere/data"),
        embedder="other-embedder",
        embedding_model="org/other-model",
        embedding_cache_dir=Path("/somewhere/cache"),
        retrieval_candidates=30,
        retrieval_top_k=7,
        min_similarity=0.83,
        llm_provider="other-llm",
        llm_timeout_seconds=12.5,
        gemini_model="gemini-other",
        gemini_api_key="secret-key",
    )


def test_defaults_apply_when_no_variable_is_set(monkeypatch: pytest.MonkeyPatch):
    for name in ENV_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("rag_etat_civil.config.load_dotenv", lambda: None)  # ignore a local .env

    assert Settings.from_env() == Settings()


def test_the_api_key_never_appears_in_the_representation_of_the_settings():
    assert "secret-key" not in repr(Settings(gemini_api_key="secret-key"))


def test_the_default_number_of_passages_is_the_one_chosen_by_the_evaluation():
    """8 is the smallest value that gives every article of the deadline cascades."""
    assert Settings().retrieval_top_k == 8
