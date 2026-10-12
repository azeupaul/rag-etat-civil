"""Tests for the language model contract and its registry."""

import pytest

from rag_etat_civil.config import Settings
from rag_etat_civil.llm.base import LLMProvider
from rag_etat_civil.llm.registry import LLM_PROVIDERS, create_llm
from tests.fakes import FakeLLM


def test_provider_interface_cannot_be_instantiated():
    with pytest.raises(TypeError):
        LLMProvider()  # type: ignore[abstract]


def test_default_provider_is_gemini():
    assert Settings().llm_provider == "gemini"


def test_unknown_provider_lists_the_available_ones(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setitem(LLM_PROVIDERS, "fake", lambda settings: FakeLLM())
    with pytest.raises(ValueError, match=r"Unknown LLM_PROVIDER 'nope'.*\['fake'\]"):
        create_llm(Settings(llm_provider="nope"))


def test_registered_provider_is_created_from_the_settings(monkeypatch: pytest.MonkeyPatch):
    llm = FakeLLM('{"ok": true}')
    monkeypatch.setitem(LLM_PROVIDERS, "fake", lambda settings: llm)
    assert create_llm(Settings(llm_provider="fake")) is llm


def test_provider_name_is_read_from_the_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    assert Settings.from_env().llm_provider == "ollama"


def test_fake_llm_returns_its_answers_in_order_and_records_the_calls():
    llm = FakeLLM("first", "second")
    schema = {"type": "object"}
    assert llm.generate_json("sys", "q1", schema) == "first"
    assert llm.generate_json("sys", "q2", schema) == "second"
    assert [call[1] for call in llm.calls] == ["q1", "q2"]


def test_fake_llm_fails_loudly_when_called_too_often():
    with pytest.raises(AssertionError, match="more times"):
        FakeLLM().generate_json("sys", "q", {})
