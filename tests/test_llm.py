import pytest
from pydantic import SecretStr

from app.agent.llm import get_llm
from app.config import settings
from app.exceptions import LLMNotConfiguredError

FAKE_KEY = "sk-or-test-1234567890"


def test_get_llm_without_key_raises_clear_error(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", SecretStr(""))
    with pytest.raises(LLMNotConfiguredError) as error:
        get_llm()
    assert "OPENROUTER_API_KEY" in error.value.message


def test_get_llm_uses_settings(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", SecretStr(FAKE_KEY))
    monkeypatch.setattr(settings, "llm_model", "some-provider/some-model")
    llm = get_llm()
    assert llm.model_name == "some-provider/some-model"
    assert llm.openai_api_base == settings.openrouter_base_url
    assert llm.temperature == settings.llm_temperature


def test_key_is_never_shown_in_printed_output(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", SecretStr(FAKE_KEY))
    assert FAKE_KEY not in repr(settings)
    assert FAKE_KEY not in str(settings)
    assert FAKE_KEY not in repr(get_llm())