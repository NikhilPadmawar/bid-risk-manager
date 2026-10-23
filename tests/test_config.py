from pathlib import Path

from pydantic import SecretStr

from app.config import Settings, settings

ENV_EXAMPLE = Path(__file__).parent.parent / ".env.example"


def example_values() -> dict[str, str]:
    lines = ENV_EXAMPLE.read_text().splitlines()
    return dict(line.split("=", 1) for line in lines if "=" in line and not line.startswith("#"))


def test_env_example_lists_every_setting():
    # If someone adds a setting but forgets .env.example, this test reminds them
    missing = [name.upper() for name in Settings.model_fields if name.upper() not in example_values()]
    assert missing == []


def test_env_example_contains_no_real_key():
    assert example_values()["OPENROUTER_API_KEY"] == "your-key-here"


def test_the_api_key_is_never_printed():
    secret = Settings(openrouter_api_key=SecretStr("sk-or-super-secret"))
    assert "sk-or-super-secret" not in repr(secret)
    assert "sk-or-super-secret" not in str(secret)
    assert "sk-or-super-secret" not in str(secret.model_dump())


def test_tests_run_without_a_real_key():
    assert settings.openrouter_api_key.get_secret_value() == ""